import asyncio
import logging
import aiocoap
from utils.config import config
from utils.coap_resources import configure as configure_coap_resources, create_coap_site
from utils import coap_client, node_registry
from utils.influxdb_connect import close_influxdb, INFLUX_BUCKET, save_to_influxdb, write_api
from utils.influxdb_connect import get_delay_state
from utils.mqtt_client import configure as configure_mqtt_client, start_mqtt_thread
from utils import energy_state
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONGESTED_PUBLISH_INTERVAL_MS = 5000
CONGESTION_CHECK_INTERVAL_S = 5.0

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
_sampling_interval_state: dict[str, int] = {}
_sensor_baseline_interval_ms: dict[str, int] = {}


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


async def _monitor_network_congestion():
    """
    Periodically inspect the moving average delay per node.

    If the average delay exceeds 500 ms, the cloud tells that sensor to slow
    down its publish interval. When the delay drops back below the threshold,
    the interval is restored.
    """
    while True:
        try:
            registered_nodes = {
                node.get("node_id"): node
                for node in node_registry.get_all_nodes()
                if node.get("node_id")
            }
            delay_state = get_delay_state()

            # Clean up stale state for nodes that are no longer registered.
            for node_id in list(_sampling_interval_state):
                if node_id not in registered_nodes:
                    _sampling_interval_state.pop(node_id, None)

            for node_id, node in registered_nodes.items():
                if node.get("type") == "battery":
                    continue

                if node_id not in _sensor_baseline_interval_ms:
                    try:
                        _sensor_baseline_interval_ms[node_id] = await coap_client.get_sampling_interval(
                            node["ip"],
                            int(node.get("port", 5683)),
                        )
                        logging.info(
                            "[Congestion] Learned baseline interval for %s: %dms",
                            node_id,
                            _sensor_baseline_interval_ms[node_id],
                        )
                    except Exception:
                        logging.exception(
                            "[Congestion] Could not read baseline interval from %s",
                            node_id,
                        )
                        continue

                state = delay_state.get(node_id)
                if not state or int(state.get("samples", 0)) < 3:
                    continue

                congested = bool(state.get("congested", False))
                target_interval = (
                    CONGESTED_PUBLISH_INTERVAL_MS
                    if congested
                    else _sensor_baseline_interval_ms[node_id]
                )

                if _sampling_interval_state.get(node_id) == target_interval:
                    continue

                reply = await coap_client.set_sampling_interval(
                    node["ip"],
                    int(node.get("port", 5683)),
                    target_interval,
                )
                _sampling_interval_state[node_id] = target_interval
                logging.info(
                    "[Congestion] node=%s avg_delay=%.1fms samples=%d state=%s -> interval=%dms reply=%s",
                    node_id,
                    float(state.get("avg_delay_ms", 0.0)),
                    int(state.get("samples", 0)),
                    "CONGESTED" if congested else "NORMAL",
                    target_interval,
                    reply,
                )
        except Exception:
            logging.exception("[Congestion] Failed to evaluate or apply adaptive sampling")

        await asyncio.sleep(CONGESTION_CHECK_INTERVAL_S)

async def run():
    protocol = await aiocoap.Context.create_client_context()
    coap_client.set_protocol(protocol)
    node_registry.configure(on_new_node_callback=coap_client.register_with_sensor,
                            event_loop=asyncio.get_running_loop())

    t1 = asyncio.create_task(start_coap_server())
    t2 = asyncio.create_task(energy_state.balance_loop())
    t3 = asyncio.create_task(_monitor_sensor_liveness())
    t4 = asyncio.create_task(_monitor_network_congestion())
    _background_tasks.update({t1, t2, t3, t4})   # riferimento forte: evita che il GC li distrugga

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
