import json
import logging

import aiocoap
import aiocoap.resource as resource
from influxdb_client import Point

save_to_influxdb = None
write_api = None
INFLUX_BUCKET = None


def configure(save_func, influx_write_api, influx_bucket):
    """Configure shared dependencies for CoAP resources."""
    global save_to_influxdb, write_api, INFLUX_BUCKET
    save_to_influxdb = save_func
    write_api = influx_write_api
    INFLUX_BUCKET = influx_bucket


class TelemetryResource(resource.Resource):
    """Endpoint that receives CoAP POST telemetry data."""

    async def render_post(self, request):
        try:
            payload_str = request.payload.decode('utf-8')
            payload = json.loads(payload_str)
            save_to_influxdb(payload)
            return aiocoap.Message(code=aiocoap.CHANGED, payload=b"ACK")
        except Exception as e:
            logging.error(f"CoAP POST Error: {e}")
            return aiocoap.Message(code=aiocoap.BAD_REQUEST, payload=b"Invalid Payload")


class RegisterResource(resource.Resource):
    """Optional endpoint for sensors to register themselves."""

    async def render_post(self, request):
        try:
            payload_str = request.payload.decode('utf-8')
            payload = json.loads(payload_str)

            logging.info(f"Received registration from Node: {payload.get('node_id')}")
            point = Point("registered_nodes") \
                .tag("node_id", payload.get("node_id")) \
                .tag("type", payload.get("type")) \
                .tag("protocol", payload.get("proto")) \
                .tag("ip_address", payload.get("ip")) \
                .tag("event_type", "register") \
                .field("status", 1)

            write_api.write(bucket=INFLUX_BUCKET, record=point)
            logging.info(f"[REGISTER] Node {payload.get('node_id')} registered successfully.")
            return aiocoap.Message(code=aiocoap.CREATED, payload=b"Registered")
        except Exception as e:
            logging.error(f"CoAP Registration Error: {e}")
            return aiocoap.Message(code=aiocoap.BAD_REQUEST, payload=b"Invalid Registration Data")


class UnregisterResource(resource.Resource):
    """Endpoint to handle device unregistering."""

    async def render_post(self, request):
        try:
            payload_str = request.payload.decode('utf-8')
            payload = json.loads(payload_str)
            node_id = payload.get("node_id")

            point = Point("device_events") \
                .tag("node_id", node_id) \
                .tag("type", payload.get("type")) \
                .tag("protocol", payload.get("proto")) \
                .tag("event_type", "unregister") \
                .field("status", 0)

            write_api.write(bucket=INFLUX_BUCKET, record=point)
            logging.info(f"[UNREGISTER] Node: {node_id} has been unregistered (maintenance/offline).")
            return aiocoap.Message(code=aiocoap.DELETED, payload=b"UNREGISTERED")
        except Exception as e:
            logging.error(f"CoAP Unregister Error: {e}")
            return aiocoap.Message(code=aiocoap.BAD_REQUEST, payload=b"Invalid")


def create_coap_site():
    """Build the CoAP resource tree."""
    root = resource.Site()
    root.add_resource(['telemetry'], TelemetryResource())
    root.add_resource(['register'], RegisterResource())
    root.add_resource(['unregister'], UnregisterResource())
    return root
