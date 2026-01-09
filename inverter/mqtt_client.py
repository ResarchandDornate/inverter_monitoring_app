import json
import logging
import paho.mqtt.client as mqtt
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings
import re
from decimal import Decimal
from django.utils import timezone
from datetime import datetime

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()
mqtt_client = None

def on_connect(client, userdata, flags, rc):
    """Callback for when the client receives a CONNACK response from the server (VERSION1)"""
    if rc == 0:
        logger.info("Connected to MQTT broker successfully")
        # Subscribe to inverter topics
        client.subscribe("inverter/+/data")
        client.subscribe("inverters_esp32c3")
        logger.info("Subscribed to MQTT topics")
    else:
        logger.error(f"Failed to connect to MQTT broker with result code {rc}")

def on_message(client, userdata, msg):
    """Handle incoming MQTT messages"""
    try:
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        logger.info(f"Received message on topic {topic}: {payload}")
        
        # Parse JSON data
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return
        
        # Extract inverter ID from topic or data
        inverter_id = extract_inverter_id_from_topic(topic)
        if not inverter_id and 'inverter_id' in data:
            inverter_id = data['inverter_id']
        
        # Save to database if it's inverter data
        if any(key in data for key in ['VG', 'IG', 'VPV', 'IPV', 'TEMP1', 'TEMP2']):
            save_inverter_data(data, inverter_id)
        
        # Send to WebSocket
        message = {
            'topic': topic,
            'data': data,
            'timestamp': data.get('timestamp', None)
        }
        
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                'inverter_updates',
                {
                    'type': 'inverter_message',
                    'message': message
                }
            )
        
    except Exception as e:
        logger.error(f"Error processing MQTT message: {e}")

def save_inverter_data(data, inverter_id):
    """Save inverter data to database with proper field mapping"""
    try:
        # Import here to avoid circular imports
        from .models import InverterData, Inverter, Manufacturer
        
        # Get or create inverter instance
        inverter_instance = get_or_create_inverter(inverter_id)
        
        # Map ESP32 data to your database model
        vg = float(data.get('VG', 0))  # Grid voltage
        ig = float(data.get('IG', 0))  # Grid current
        vpv = float(data.get('VPV', 0))  # PV voltage
        ipv = float(data.get('IPV', 0))  # PV current
        temp1 = float(data.get('TEMP1', 0))  # Temperature 1
        temp2 = float(data.get('TEMP2', 0))  # Temperature 2
        
        # Calculate power (P = V * I)
        grid_power = vg * ig  # Grid power
        pv_power = vpv * ipv  # PV power
        
        # Use the higher voltage (grid or PV) as main voltage
        main_voltage = max(vg, vpv)
        # Use the higher current (grid or PV) as main current  
        main_current = max(ig, ipv)
        # Use the higher power as main power
        main_power = max(grid_power, pv_power)
        # Use average temperature
        avg_temperature = (temp1 + temp2) / 2
        
        # Handle timestamp - ESP32 sends milliseconds since boot, convert to Django datetime
        esp32_timestamp = data.get('timestamp', None)
        if esp32_timestamp:
            # ESP32 timestamp is milliseconds since boot, we'll use current time instead
            # since we can't convert boot time to real time without knowing boot time
            record_timestamp = timezone.now()
            logger.info(f"ESP32 timestamp: {esp32_timestamp}ms, using current time: {record_timestamp}")
        else:
            record_timestamp = timezone.now()
        
        # Create database record with timestamp
        inverter_data = InverterData.objects.create(
            inverter=inverter_instance,
            manufacturer=inverter_instance.manufacturer,
            voltage=Decimal(str(round(main_voltage, 2))),
            current=Decimal(str(round(main_current, 2))),
            power=Decimal(str(round(main_power, 2))),
            temperature=avg_temperature,
            grid_connected=vg > 200,  # Assume grid connected if voltage > 200V
            timestamp=record_timestamp  # Add the timestamp field
        )
        
        logger.info(f"SUCCESS: Saved inverter data to database: ID={inverter_data.id}, "
                   f"V={main_voltage}V, I={main_current}A, P={main_power}W, T={avg_temperature}C, "
                   f"Time={record_timestamp}")
        
        # Also log the detailed data for debugging
        logger.info(f"DETAILS: Grid: {vg}V/{ig}A/{grid_power}W, "
                   f"PV: {vpv}V/{ipv}A/{pv_power}W, Temps: {temp1}C/{temp2}C")
        
    except Exception as e:
        logger.error(f"Failed to save inverter data to database: {e}")
        logger.error(f"Data received: {data}")
        # Print the full error for debugging
        import traceback
        logger.error(f"Full error: {traceback.format_exc()}")

def get_or_create_inverter(inverter_id):
    """Get or create an inverter instance"""
    try:
        from .models import Inverter, Manufacturer
        
        # Try to get existing inverter
        try:
            inverter = Inverter.objects.get(serial_number=inverter_id)
            return inverter
        except Inverter.DoesNotExist:
            pass
        
        # Get or create manufacturer
        manufacturer, created = Manufacturer.objects.get_or_create(
            name="ESP32",
            defaults={
                'country': 'Unknown',
                'website': 'https://espressif.com'
            }
        )
        
        if created:
            logger.info(f"Created new manufacturer: {manufacturer.name}")
        
        # Create new inverter
        inverter = Inverter.objects.create(
            manufacturer=manufacturer,
            model=f"ESP32-{inverter_id}",
            serial_number=inverter_id,
            capacity=5000,  # Default 5kW capacity
            installation_date='2024-01-01'
        )
        
        logger.info(f"Created new inverter: {inverter.model} (ID: {inverter_id})")
        return inverter
        
    except Exception as e:
        logger.error(f"Error getting/creating inverter: {e}")
        # Return None and let the calling function handle it
        raise

def extract_inverter_id_from_topic(topic):
    """Extract inverter ID from MQTT topic: inverter/<id>/data or inverters_esp32c3"""
    match = re.search(r'inverter/([^/]+)/data', topic)
    if match:
        return match.group(1)
    if topic == "inverters_esp32c3":
        return "esp32c3"
    return None

def start_mqtt_client():
    """Start the MQTT client and connect to the broker"""
    global mqtt_client
    try:
        # Use the simple client without callback API version for compatibility
        mqtt_client = mqtt.Client(client_id=settings.MQTT_CLIENT_ID)
        
        # Set callbacks
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message

        # Set credentials if provided
        if hasattr(settings, 'MQTT_USERNAME') and hasattr(settings, 'MQTT_PASSWORD'):
            mqtt_client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

        # Connect to broker
        mqtt_client.connect(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, 60)
        mqtt_client.loop_start()
        logger.info(f"Started MQTT client, connected to {settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}")
        return mqtt_client
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {str(e)}")
        return None

def stop_mqtt_client():
    """Stop the MQTT client"""
    global mqtt_client
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        logger.info("MQTT client stopped")
        mqtt_client = None

def publish_to_mqtt(topic, payload):
    """Publish message to MQTT broker"""
    global mqtt_client
    if mqtt_client and mqtt_client.is_connected():
        try:
            result = mqtt_client.publish(topic, json.dumps(payload))
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published to {topic}: {payload}")
                return True
            else:
                logger.error(f"Failed to publish to {topic}: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"Error publishing to MQTT: {e}")
            return False
    else:
        logger.error("MQTT client not connected")
        return False
