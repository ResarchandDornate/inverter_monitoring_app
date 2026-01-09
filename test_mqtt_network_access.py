import paho.mqtt.client as mqtt
import socket

def test_mqtt_connection():
    # Test if MQTT port is accessible
    mqtt_server = "192.168.34.23"  # Your computer's IP
    mqtt_port = 1883
    
    print(f"Testing MQTT connection to {mqtt_server}:{mqtt_port}")
    
    try:
        # Test socket connection first
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((mqtt_server, mqtt_port))
        sock.close()
        
        if result == 0:
            print("✓ Port 1883 is accessible")
        else:
            print("✗ Port 1883 is not accessible")
            print("Check firewall and Mosquitto configuration")
            return False
            
    except Exception as e:
        print(f"✗ Socket test failed: {e}")
        return False
    
    # Test MQTT connection
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="network_test_client")
        client.connect(mqtt_server, mqtt_port, 60)
        client.publish("test/connection", "Hello from network test")
        client.disconnect()
        print("✓ MQTT connection successful")
        return True
        
    except Exception as e:
        print(f"✗ MQTT connection failed: {e}")
        return False

if __name__ == "__main__":
    test_mqtt_connection()