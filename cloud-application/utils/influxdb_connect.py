import logging
import time

from influxdb_client import InfluxDBClient, Point, WriteOptions
from utils.config import config

# Per-node minimum observed gap (received_ms - sent_ms).
# The minimum represents the best-case transit latency for each node.
# delay_ms = current_gap - min_gap, so it is always >= 0.
# Updated whenever a faster packet is seen — this makes the baseline converge
# to the true minimum network latency over time.
_mqtt_offsets: dict[str, int] = {}

influx_config = config["influxdb"]
INFLUX_URL = influx_config["url"]
INFLUX_TOKEN = influx_config["token"]
INFLUX_ORG = influx_config["org"]
INFLUX_BUCKET = influx_config["bucket"]

def _on_write_error(conf, data, exception):
    logging.error(
        f"[InfluxDB] Batch write FAILED — "
        f"status={getattr(exception, 'status', '?')} "
        f"reason={getattr(exception, 'reason', '?')} "
        f"body={getattr(exception, 'body', str(exception))}"
    )

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(
    write_options=WriteOptions(
        batch_size=influx_config.get("batch_size", 100),
        flush_interval=influx_config.get("flush_interval", 1000),
    ),
    error_callback=_on_write_error,
)


def save_to_influxdb(payload, received_ms: int | None = None):
    """Shared function to parse JSON and write it into InfluxDB.
    
    received_ms: arrival timestamp in ms. When called from MQTT, pass this
    from on_message to avoid measuring queue processing delay. When called
    from CoAP, omit it and it defaults to now.
    """
    if received_ms is None:
        received_ms = int(time.time() * 1000)
    node_id = payload.get("node_id")
    sensor_uptime_ms = int(payload.get("sent_ms", 0))
    current_gap = received_ms - sensor_uptime_ms

    # Update the per-node minimum gap whenever a faster packet arrives.
    # Using the minimum ensures delay_ms is always >= 0 and represents
    # real extra latency, not noise from a slow first packet.
    if node_id not in _mqtt_offsets or current_gap < _mqtt_offsets[node_id]:
        if node_id in _mqtt_offsets:
            logging.info(
                f"[Delay] Updated min offset for '{node_id}': "
                f"{_mqtt_offsets[node_id]} → {current_gap} ms"
            )
        else:
            logging.info(
                f"[Delay] Calibrated offset for '{node_id}': {current_gap} ms"
            )
        _mqtt_offsets[node_id] = current_gap

    # delay_ms = extra latency on top of the best-case transit time.
    # Always >= 0. Near-zero means ideal; growing means congestion.
    delay_ms = current_gap - _mqtt_offsets[node_id]

    try:
        point = (
            Point("telemetry_raw")
            .tag("node_id", payload.get("node_id"))
            .tag("type", payload.get("type"))
            .tag("protocol", payload.get("proto"))
            .tag("ip_address", payload.get("ip"))
            .field("seq", int(payload.get("seq", 0)))
            .field("voltage", float(payload.get("v", 0.0)))
            .field("current", float(payload.get("i", 0.0)))
            .field("power", float(payload.get("v", 0.0)) * float(payload.get("i", 0.0)))
            .field("ml_anomaly", int(payload.get("anomaly", 0)))
            .field("publish_interval_ms", int(payload.get("publish_interval_ms", 0)))
            .field("sent_at_ms", int(payload.get("sent_ms", 0)))
            .field("delay_ms", float(delay_ms))
            .field("adaptive_mode", payload.get("mode", "normal"))
            .field("status", payload.get("status", "UNKNOWN"))
        )

        if "soc" in payload:
            point.field("soc", float(payload["soc"]))

        write_api.write(bucket=INFLUX_BUCKET, record=point)
        logging.info(f"[TELEMETRY] Data saved from [{payload.get('proto')}] Node: {payload.get('node_id')}")
    except Exception as e:
        logging.error(f"Error parsing or saving data: {e}")


def close_influxdb():
    """Close InfluxDB client resources."""
    write_api.close()
    client.close()
