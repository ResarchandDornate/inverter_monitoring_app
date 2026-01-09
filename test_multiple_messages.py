import paho.mqtt.client as mqtt
import json
import time
import random

def send_multiple_messages():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="multi_test_publisher")
    
    try:
        client.connect("localhost", 1883, 60)
        print("Connected to MQTT broker")
        
        # Send 5 test messages with different data
        for i in range(5):
            test_data = {
                "inverter_id": f"esp32c3_0{i+1}",
                "VG": round(240 + random.uniform(-10, 10), 1),
                "IG": round(8 + random.uniform(-2, 2), 1),
                "VPV": round(48 + random.uniform(-5, 5), 1),
                "IPV": round(9 + random.uniform(-1, 1), 1),
                "TEMP1": round(25 + random.uniform(-3, 8), 1),
                "TEMP2": round(26 + random.uniform(-3, 8), 1)
            }
            
            topic = f"inverter/esp32c3_0{i+1}/data"
            payload = json.dumps(test_data)
            
            print(f"Sending message {i+1}/5 to {topic}")
            result = client.publish(topic, payload)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"  ✓ Published: VG={test_data['VG']}V")
            else:
                print(f"  ✗ Failed to publish")
            
            time.sleep(2)  # Wait 2 seconds between messages
        
        client.disconnect()
        print("All messages sent!")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    send_multiple_messages()