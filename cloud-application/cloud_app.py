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

_background_tasks = set()


async def _monitor_sensor_liveness():
    """
    Active heartbeat loop.

    Every 10 seconds, probe each registered node with CoAP:
    - battery nodes: GET /actuators/battery
    - all other nodes: GET /actuators/status

    If a node does not answer, remove it from the registry so the energy
    balance no longer uses it.
    """
    probe_interval_s = 10.0

    while True:
        nodes = node_registry.get_all_nodes()
        for node in nodes:
            node_id = node.get("node_id", "unknown")
            alive = await coap_client.probe_node(node, timeout_s=3.0)
            if not alive:
                logging.warning(
                    f"[Failure] Node '{node_id}' did not respond to CoAP heartbeat. "
                    "Removing from registry."
                )
                node_registry.remove_node(node_id)
        await asyncio.sleep(probe_interval_s)

async def run():
    protocol = await aiocoap.Context.create_client_context()
    coap_client.set_protocol(protocol)
    node_registry.configure(on_new_node_callback=coap_client.register_with_sensor,
                            event_loop=asyncio.get_running_loop())

    t1 = asyncio.create_task(start_coap_server())
    t2 = asyncio.create_task(energy_state.balance_loop())
    t3 = asyncio.create_task(_monitor_sensor_liveness())
    _background_tasks.update({t1, t2, t3})   # riferimento forte: evita che il GC li distrugga

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
