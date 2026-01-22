"""MQTT client integration for inverter monitoring.

This module is responsible for:
* Connecting to the Mosquitto broker
* Subscribing to inverter topics
* Processing messages synchronously (Redis/Celery removed for cost optimization)
* Broadcasting real-time updates via Channels
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

import paho.mqtt.client as mqtt
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings

from .services import (
    extract_inverter_id,
    generate_message_id,
    should_save_message,
    validate_inverter_message,
    normalize_inverter_data,
    build_inverter_data_kwargs,
)
from .models import Inverter, InverterData
from django.db import transaction

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()

# Shared client instance used by the application
mqtt_client: Optional[mqtt.Client] = None

# Simple metrics for health checks
last_message_timestamp: Optional[float] = None
consecutive_connect_failures: int = 0


def on_connect(client, userdata, flags, rc):
    """Callback when the client receives a CONNACK from the broker."""
    global consecutive_connect_failures

    if rc == 0:
        consecutive_connect_failures = 0
        logger.info("Connected to MQTT broker successfully")
        client.subscribe("inverter/+/data")
        client.subscribe("inverters_esp32c3")
        logger.info("Subscribed to MQTT topics")
    else:
        consecutive_connect_failures += 1
        logger.error("Failed to connect to MQTT broker (rc=%s)", rc)


def on_message(client, userdata, msg):
    """Handle incoming MQTT messages quickly and delegate work."""
    global last_message_timestamp

    topic = msg.topic
    payload = msg.payload.decode("utf-8")
    message_id = generate_message_id()
    last_message_timestamp = time.time()

    logger.info(
        "MQTT message received",
        extra={
            "component": "mqtt_client",
            "topic": topic,
            "message_id": message_id,
        },
    )

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        logger.warning(
            "Failed to parse MQTT payload as JSON",
            extra={"component": "mqtt_client", "topic": topic, "message_id": message_id},
        )
        return

    if not should_save_message(data):
        logger.debug(
            "Message skipped by filter",
            extra={"component": "mqtt_client", "topic": topic, "message_id": message_id},
        )
        return

    cleaned = validate_inverter_message(data)
    inverter_id = extract_inverter_id(topic, data)

    # Process message synchronously (Redis/Celery removed for cost optimization)
    try:
        _process_inverter_message_sync(
            message_id=message_id, topic=topic, data=cleaned, inverter_id=inverter_id
        )
    except Exception as exc:
        logger.error(
            "Failed to process MQTT message: %s",
            exc,
            extra={"component": "mqtt_client", "topic": topic, "message_id": message_id},
            exc_info=True,
        )

    # Broadcast to WebSocket subscribers with the raw data so the UI
    # can display immediately while the database write is in progress.
    message = {
        "topic": topic,
        "data": data,
        "timestamp": data.get("timestamp"),
        "message_id": message_id,
    }

    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            "inverter_updates",
            {
                "type": "inverter_message",
                "message": message,
            },
        )


def start_mqtt_client(max_retries: int = 5, base_delay: float = 2.0):
    """Start the MQTT client and connect to the broker with retry logic."""
    global mqtt_client

    client = mqtt.Client(client_id=settings.MQTT_CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message

    if getattr(settings, "MQTT_USERNAME", None) and getattr(
        settings, "MQTT_PASSWORD", None
    ):
        client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

    attempt = 0
    while True:
        try:
            client.connect(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, 60)
            client.loop_start()
            mqtt_client = client
            logger.info(
                "Started MQTT client, connected to %s:%s",
                settings.MQTT_BROKER_HOST,
                settings.MQTT_BROKER_PORT,
            )
            return mqtt_client
        except Exception as exc:
            attempt += 1
            logger.error(
                "Failed to connect to MQTT broker (attempt %s/%s): %s",
                attempt,
                max_retries,
                exc,
            )
            if max_retries and attempt >= max_retries:
                logger.error("Giving up connecting to MQTT broker after %s attempts", attempt)
                return None
            sleep_for = base_delay * (2 ** (attempt - 1))
            time.sleep(min(sleep_for, 60))


def stop_mqtt_client():
    """Stop the MQTT client loop and disconnect from the broker."""
    global mqtt_client
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        logger.info("MQTT client stopped")
        mqtt_client = None


def publish_to_mqtt(topic, payload):
    """Publish a JSON payload to the MQTT broker."""
    if mqtt_client and mqtt_client.is_connected():
        try:
            result = mqtt_client.publish(topic, json.dumps(payload))
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug("Published MQTT message", extra={"topic": topic})
                return True
            logger.error("Failed to publish MQTT message (rc=%s)", result.rc)
        except Exception as exc:
            logger.error("Error publishing to MQTT: %s", exc)
    else:
        logger.error("MQTT client not connected")
    return False


def get_last_message_timestamp() -> Optional[float]:
    """Return the Unix timestamp of the last received MQTT message, if any."""
    return last_message_timestamp


def _process_inverter_message_sync(
    message_id: str, topic: str, data: dict, inverter_id: Optional[str] = None
) -> None:
    """Process inverter message synchronously (replaces Celery task).
    
    Args:
        message_id: Correlation ID for tracing logs
        topic: MQTT topic
        data: Cleaned numeric payload
        inverter_id: Optional inverter identifier
    """
    if not inverter_id:
        logger.warning(
            "MQTT message dropped: could not determine inverter_id",
            extra={"component": "mqtt_client", "topic": topic, "message_id": message_id},
        )
        return

    normalized = normalize_inverter_data(inverter_id, data)
    
    with transaction.atomic():
        inverter = _get_or_create_inverter(inverter_id)
        kwargs = build_inverter_data_kwargs(normalized, inverter)
        inverter_data = InverterData.objects.create(**kwargs)

    logger.info(
        "Inverter data persisted",
        extra={
            "component": "mqtt_client",
            "topic": topic,
            "message_id": message_id,
            "inverter_id": inverter_id,
            "record_id": inverter_data.id,
        },
    )


def _get_or_create_inverter(inverter_id: str):
    """Get or create an Inverter instance.
    
    When creating a new inverter automatically from MQTT data, only the
    serial_number is required. All other fields are optional.
    """
    try:
        return Inverter.objects.get(serial_number=inverter_id)
    except Inverter.DoesNotExist:
        # Try to find a default manufacturer
        manufacturer = None
        try:
            from .models import Manufacturer
            manufacturer = Manufacturer.objects.filter(
                company_name__icontains="ESP32"
            ).first()
            if not manufacturer:
                manufacturer, _ = Manufacturer.objects.get_or_create(
                    company_name="ESP32",
                    defaults={
                        "country": "Unknown",
                        "website": "https://espressif.com"
                    }
                )
        except Exception as e:
            logger.warning(
                "Could not set manufacturer for new inverter",
                extra={"inverter_id": inverter_id, "error": str(e)}
            )

        inverter = Inverter.objects.create(
            manufacturer=manufacturer,
            serial_number=inverter_id,
            name=f"Inverter {inverter_id}",
            model=f"ESP32-{inverter_id}",
        )
        logger.info(
            "Created inverter on-the-fly from MQTT data",
            extra={
                "inverter_id": inverter_id,
                "component": "mqtt_client"
            }
        )
        return inverter

