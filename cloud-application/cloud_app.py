import asyncio
import logging
import aiocoap
from utils.config import config
from utils.coap_resources import configure as configure_coap_resources, create_coap_site
from utils import coap_client, node_registry
from utils.influxdb_connect import close_influxdb, INFLUX_BUCKET, save_to_influxdb, write_api
from utils.mqtt_client import configure as configure_mqtt_client, start_mqtt_thread
from utils import energy_state
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==========================================
# INITIALISE MODULES
# ==========================================
configure_coap_resources(save_to_influxdb, write_api, INFLUX_BUCKET)
configure_mqtt_client(save_to_influxdb)

# When a sensor POSTs to /register, the registry calls register_with_sensor()
# automatically — the cloud subscribes (Observe) back to that sensor.
node_registry.configure(on_new_node_callback=coap_client.register_with_sensor)


# ==========================================
# CoAP SERVER  (sensors → cloud)
# ==========================================

async def start_coap_server():
    root = create_coap_site()
    coap_config = config.get("coap", {})
    bind_host = coap_config.get("bind_host", "::")
    bind_port = coap_config.get("bind_port", 5683)
    await aiocoap.Context.create_server_context(root, bind=(bind_host, bind_port))
    logging.info(f"CoAP Server listening on [{bind_host}]:{bind_port}")
    logging.info("  Endpoints: /register  /unregister  /telemetry")
    await asyncio.get_running_loop().create_future()


# ==========================================
# LED CONTROL ENDPOINT  (cloud → sensor)
# ==========================================
# Exposed at:  coap://<cloud>/actuators/leds
#
# PUT/POST payload (JSON):
#   {"node_id": "<id>", "color": "r|g|b", "mode": "on|off"}
#
# The cloud looks up the node in the registry by node_id,
# then forwards a PUT to that sensor's actuators/leds resource.
# ------------------------------------------------------------------
# Example (from aiocoap-client or coap-example-client):
#   PUT coap://<cloud_ip>:5683/actuators/leds
#   payload: {"node_id":"fd00::202:2:2:2","color":"g","mode":"on"}


# ==========================================
# MAIN
# ==========================================

async def run():
   async def run():
    protocol = await aiocoap.Context.create_client_context()
    coap_client.set_protocol(protocol)

    asyncio.create_task(start_coap_server())
    asyncio.create_task(energy_state.balance_loop())   # ← aggiunta

    await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    logging.info("--- Starting IoT Cloud Application ---")
    start_mqtt_thread()
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logging.info("Cloud Application stopped by user (Ctrl+C).")
    finally:
        close_influxdb()
        logging.info("InfluxDB connection closed.")
