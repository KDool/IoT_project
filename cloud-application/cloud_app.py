import asyncio
import json
import logging
import aiocoap
from utils.config import config
from utils.coap_resources import configure as configure_coap_resources, create_coap_site
from utils.influxdb_connect import close_influxdb, INFLUX_BUCKET, save_to_influxdb, write_api
from utils.mqtt_client import configure as configure_mqtt_client, start_mqtt_thread

# Enable logging to simplify debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==========================================
# 1. INFLUXDB CONFIGURATION (Optimized for stress testing)
# ==========================================
# Configuration and write client are managed in utils/influxdb_connect.py

configure_coap_resources(save_to_influxdb, write_api, INFLUX_BUCKET)
configure_mqtt_client(save_to_influxdb)


# ==========================================
# 3. CoAP SERVER MODULE (Runs with Asyncio)
# ==========================================


async def start_coap_server():
    root = create_coap_site()
    coap_config = config.get("coap", {})
    bind_host = coap_config.get("bind_host", "::")
    bind_port = coap_config.get("bind_port", 5683)

    await aiocoap.Context.create_server_context(root, bind=(bind_host, bind_port))
    logging.info(f"CoAP Server has started listening on port {bind_port} (IPv6/IPv4).")
    await asyncio.get_running_loop().create_future()


# ==========================================
# 4. RUN THE WHOLE SYSTEM
# ==========================================
if __name__ == "__main__":
    logging.info("--- Starting IoT Cloud Application ---")
    
    # 1. Start the background MQTT listener thread
    start_mqtt_thread()
    
    # 2. Start the main CoAP event loop
    try:
        asyncio.run(start_coap_server())
    except KeyboardInterrupt:
        logging.info("Cloud Application stopped by user (Ctrl+C).")
    finally:
        # Clean up resources before shutting down
        close_influxdb()
        logging.info("Safe shutdown connection to InfluxDB completed.")
