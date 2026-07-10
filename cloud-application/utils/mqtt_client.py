import json
import logging
import time

import paho.mqtt.client as mqtt
from utils.config import config
from utils import energy_state

mqtt_config = config["mqtt"]

save_to_influxdb = None
MQTT_BROKER = mqtt_config.get("broker", "localhost")
MQTT_PORT = mqtt_config.get("port", 1883)
MQTT_TOPIC = mqtt_config.get("topic", "iot/telemetry")
MQTT_CLIENT_ID = mqtt_config.get("client_id", "cloud_app_subscriber")


def configure(save_func, broker=None, port=None, topic=None, client_id=None):
    """Configure MQTT client settings and the shared save callback."""
    global save_to_influxdb, MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, MQTT_CLIENT_ID
    save_to_influxdb = save_func
    if broker is not None:
        MQTT_BROKER = broker
    if port is not None:
        MQTT_PORT = port
    if topic is not None:
        MQTT_TOPIC = topic
    if client_id is not None:
        MQTT_CLIENT_ID = client_id


def on_connect(client, userdata, flags, rc):
    logging.info(f"MQTT Broker connected with code: {rc}")
    client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, msg):
    # Capture arrival time immediately — before any processing delay.
    received_ms = int(time.time() * 1000)
    try:
        payload_str = msg.payload.decode('utf-8')
        payload = json.loads(payload_str)
        save_to_influxdb(payload, received_ms)
        energy_state.update_reading(payload)
    except json.JSONDecodeError:
        logging.warning("MQTT received data that is not valid JSON!")

def start_mqtt_thread():
    if save_to_influxdb is None:
        raise RuntimeError("MQTT client is not configured with save_to_influxdb")

    mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        logging.info("MQTT Listener has started in a background thread.")
    except Exception as e:
        logging.error(f"Failed to connect to MQTT Broker: {e}")
