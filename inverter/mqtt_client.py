"""
MQTT client integration for inverter monitoring.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional
import ssl

import paho.mqtt.client as mqtt
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.conf import settings
from django.db import transaction
from django.contrib.auth import get_user_model

from .models import Inverter, InverterData, Manufacturer
from .services import (
    extract_inverter_id,
    generate_message_id,
    should_save_message,
    validate_inverter_message,
    normalize_inverter_data,
    build_inverter_data_kwargs,
)

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()

mqtt_client: Optional[mqtt.Client] = None
last_message_timestamp: Optional[float] = None


# -------------------------------------------------------------------
# MQTT CALLBACKS
# -------------------------------------------------------------------

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT broker successfully")

        res, mid = client.subscribe("inverter/+/data")
        logger.info("SUBSCRIBE inverter/+/data result=%s mid=%s", res, mid)

        res, mid = client.subscribe("inverter/esp32c3_client/data")
        logger.info("SUBSCRIBE inverter/esp32c3_client/data result=%s mid=%s", res, mid)
    else:
        logger.error("MQTT connection failed rc=%s", rc)


def on_message(client, userdata, msg):
    global last_message_timestamp

    topic = msg.topic
    payload = msg.payload.decode("utf-8")
    message_id = generate_message_id()
    last_message_timestamp = time.time()

    logger.info("MQTT message received", extra={"topic": topic})

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON payload")
        return

    if not should_save_message(data):
        return

    cleaned = validate_inverter_message(data)
    inverter_id = extract_inverter_id(topic, data)

    if not inverter_id:
        logger.warning("Could not extract inverter_id")
        return

    try:
        _process_inverter_message_sync(message_id, topic, cleaned, inverter_id)
    except Exception:
        logger.exception("Failed to process MQTT message")

    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            "inverter_updates",
            {
                "type": "inverter_message",
                "message": {
                    "topic": topic,
                    "data": data,
                    "timestamp": data.get("timestamp"),
                    "message_id": message_id,
                },
            },
        )


# -------------------------------------------------------------------
# MQTT CLIENT CONTROL
# -------------------------------------------------------------------


def start_mqtt_client():
    global mqtt_client

    client = mqtt.Client(client_id=settings.MQTT_CLIENT_ID)

    client.on_connect = on_connect
    client.on_message = on_message

    client.username_pw_set(
        settings.MQTT_USERNAME,
        settings.MQTT_PASSWORD,
    )

    client.tls_set(
        ca_certs="/etc/ssl/certs/ca-certificates.crt",
        tls_version=ssl.PROTOCOL_TLSv1_2,
    )

    client.tls_insecure_set(False)

    while True:
        try:
            client.connect(
                settings.MQTT_BROKER_HOST,
                8883,
                keepalive=60,
            )
            client.loop_forever()
        except Exception:
            logger.exception("MQTT crashed, retrying in 5 seconds")
            time.sleep(5)



def stop_mqtt_client():
    global mqtt_client
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        mqtt_client = None


def get_last_message_timestamp():
    return last_message_timestamp


# -------------------------------------------------------------------
# MESSAGE PROCESSING
# -------------------------------------------------------------------

def _process_inverter_message_sync(
    message_id: str,
    topic: str,
    data: dict,
    inverter_id: str,
):
    normalized = normalize_inverter_data(inverter_id, data)

    with transaction.atomic():
        inverter = _get_or_create_inverter(inverter_id)
        kwargs = build_inverter_data_kwargs(normalized, inverter)
        record = InverterData.objects.create(**kwargs)

    logger.info(
        "Inverter data persisted",
        extra={"inverter_id": inverter_id, "record_id": record.id},
    )


# -------------------------------------------------------------------
# DOMAIN HELPERS
# -------------------------------------------------------------------

def _get_or_create_inverter(inverter_id: str) -> Inverter:
    try:
        return Inverter.objects.get(serial_number=inverter_id)

    except Inverter.DoesNotExist:
        User = get_user_model()

        system_user, _ = User.objects.get_or_create(
            email="krishna@ornatesolar.in",
            defaults={
                "is_active": True,
                "is_verified": True,
                "role": User.ADMIN,
                "department": "Resarch and Development",
                "contact_number": "9550434470",
            },
        )

        manufacturer, _ = Manufacturer.objects.get_or_create(
            company_name="ORNATE SOLAR",
            defaults={
                "country": "INDIA",
                "website": "https://ornatesolar.com/",
            },
        )

        inverter = Inverter.objects.create(
            user=system_user,
            manufacturer=manufacturer,
            serial_number=inverter_id,
            name=f"Inverter {inverter_id}",
            model=f"ESP32-{inverter_id}",
        )

        logger.info("Created inverter from MQTT", extra={"inverter_id": inverter_id})
        return inverter
