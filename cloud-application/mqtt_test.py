import paho.mqtt.client as mqtt
import json
import time

# MQTT Broker configuration
BROKER = "localhost"
PORT = 1883
TOPIC = "iot/telemetry"

payload = {
    "node_id": "test_wind_01",
    "type": "wind",
    "proto": "MQTT",
    "ip": "fd00::2",
    "v": 48.5, 
    "i": 10.2, 
    "anomaly": 0,
    "sent_ms": int(time.time() * 1000), # Lấy thời gian hiện tại chuẩn mili-giây
    "mode": "normal"
}

# Send data to MQTT Broker
client = mqtt.Client(client_id="mock_sensor_mqtt")
client.connect(BROKER, PORT, 60)

# Change dict to JSON string and publish
client.publish(TOPIC, json.dumps(payload))
print(f"Published to topic '{TOPIC}':\n{payload}")

client.disconnect()