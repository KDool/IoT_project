import logging
import time

from influxdb_client import InfluxDBClient, Point, WriteOptions
from utils.config import config
from utils.node_registry import get_node_by_id

influx_config = config["influxdb"]
INFLUX_URL = influx_config["url"]
INFLUX_TOKEN = influx_config["token"]
INFLUX_ORG = influx_config["org"]
INFLUX_BUCKET = influx_config["bucket"]

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(
    write_options=WriteOptions(
        batch_size=influx_config.get("batch_size", 100),
        flush_interval=influx_config.get("flush_interval", 1000),
    )
)


def save_to_influxdb(payload):
    """Shared function to parse JSON and write it into InfluxDB."""
    received_ms = int(time.time() * 1000)
    delay_ms = 0
    
    node = get_node_by_id(payload.get("node_id"))
    if node and "time_offset" in node:
        sensor_real_time = payload.get("sent_ms", 0) + node["time_offset"]
        delay_ms = received_ms - sensor_real_time

    try:
        point = (
            Point("telemetry_raw")
            .tag("node_id", payload.get("node_id"))
            .tag("type", payload.get("type"))
            .tag("protocol", payload.get("proto"))
            .tag("ip_address", payload.get("ip"))
            .field("voltage", float(payload.get("v", 0.0)))
            .field("current", float(payload.get("i", 0.0)))
            .field("power", float(payload.get("v", 0.0) * payload.get("i", 0.0)))
            .field("ml_anomaly", int(payload.get("anomaly", 0)))
            .field("sent_at_ms", int(payload.get("sent_ms", 0)))
            .field("delay_ms", float(delay_ms))
            .field("adaptive_mode", payload.get("mode", "normal"))
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
