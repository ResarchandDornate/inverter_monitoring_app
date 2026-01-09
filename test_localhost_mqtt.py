import paho.mqtt.client as mqtt
import time

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("SUCCESS: Connected to MQTT broker!")
        client.subscribe("test/topic")
    else:
        print(f"FAILED: Connection failed with code {rc}")

def on_message(client, userdata, msg):
    print(f"Received: {msg.topic} -> {msg.payload.decode()}")

# Test connection
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    print("Connecting to localhost:1883...")
    client.connect("localhost", 1883, 60)
    client.loop_start()
    
    # Send test message
    time.sleep(1)
    client.publish("test/topic", "Hello from Python!")
    
    # Keep alive for a few seconds
    time.sleep(3)
    client.loop_stop()
    client.disconnect()
    print("Test completed successfully!")
    
except Exception as e:
    print(f"Error: {e}")