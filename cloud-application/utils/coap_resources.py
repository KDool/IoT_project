import json
import logging

import aiocoap
import aiocoap.resource as resource
from influxdb_client import Point
from utils import node_registry
from utils import coap_client
from utils import energy_state

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
        energy_state.update_reading(payload)   # ← aggiunta
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
            logging.info(f"[REGISTER] Node '{payload.get('node_id')}' at {payload.get('ip')} registered.")

            # Add to in-memory registry → triggers cloud to subscribe back to this sensor
            node_registry.add_node(payload)

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
            node_registry.remove_node(node_id)
            logging.info(f"[UNREGISTER] Node '{node_id}' has been unregistered.")
            return aiocoap.Message(code=aiocoap.DELETED, payload=b"UNREGISTERED")
        except Exception as e:
            logging.error(f"CoAP Unregister Error: {e}")
            return aiocoap.Message(code=aiocoap.BAD_REQUEST, payload=b"Invalid")


class LedControlResource(resource.Resource):
    """
    Cloud-side LED control endpoint.

    PUT/POST coap://<cloud>/actuators/leds
    Payload (JSON): {"node_id": "<id>", "color": "r|g|b", "mode": "on|off"}

    The cloud looks up the node in the registry by node_id,
    then forwards PUT coap://<sensor>/actuators/leds?color=<c>  body: mode=<m>.
    """

    async def render_put(self, request):
        return await self._handle(request)

    async def render_post(self, request):
        return await self._handle(request)

    async def _handle(self, request):
        try:
            payload = json.loads(request.payload.decode("utf-8"))
        except Exception:
            return aiocoap.Message(
                code=aiocoap.BAD_REQUEST, payload=b"Invalid JSON payload"
            )

        node_id = payload.get("node_id")
        color   = payload.get("color")
        mode    = payload.get("mode")

        if not node_id or not color or not mode:
            return aiocoap.Message(
                code=aiocoap.BAD_REQUEST,
                payload=b"Missing field(s). Required: node_id, color, mode"
            )

        node = node_registry.get_node_by_id(node_id)
        if node is None:
            logging.warning(f"[LED] Unknown node_id '{node_id}'")
            return aiocoap.Message(
                code=aiocoap.NOT_FOUND,
                payload=f"Node '{node_id}' not registered".encode()
            )

        ip   = node["ip"]
        port = int(node.get("port", 5683))

        logging.info(
            f"[LED] Forwarding command → node '{node_id}' "
            f"({ip}:{port})  color={color}  mode={mode}"
        )

        try:
            reply = await coap_client.set_led(ip, port, color, mode)
            return aiocoap.Message(
                code=aiocoap.CHANGED, payload=reply.encode()
            )
        except ValueError as e:
            return aiocoap.Message(code=aiocoap.BAD_REQUEST, payload=str(e).encode())
        except Exception as e:
            logging.error(f"[LED] Failed to reach node '{node_id}': {e}")
            return aiocoap.Message(
                code=aiocoap.SERVICE_UNAVAILABLE,
                payload=f"Could not reach node: {e}".encode()
            )


class StatusControlResource(resource.Resource):
    """
    Cloud-side device status control endpoint.

    PUT/POST coap://<cloud>/actuators/status
    Payload (JSON): {"node_id": "<id>", "status": "on|off"}

    The cloud looks up the node in the registry by node_id,
    then forwards PUT coap://<sensor>/actuators/status  body: on|off.
    """

    async def render_put(self, request):
        return await self._handle(request)

    async def render_post(self, request):
        return await self._handle(request)

    async def _handle(self, request):
        try:
            payload = json.loads(request.payload.decode("utf-8"))
        except Exception:
            return aiocoap.Message(
                code=aiocoap.BAD_REQUEST, payload=b"Invalid JSON payload"
            )

        node_id = payload.get("node_id")
        status  = payload.get("status")

        if not node_id or not status:
            return aiocoap.Message(
                code=aiocoap.BAD_REQUEST,
                payload=b"Missing field(s). Required: node_id, status"
            )

        if status.lower() not in ("on", "off"):
            return aiocoap.Message(
                code=aiocoap.BAD_REQUEST,
                payload=b"Invalid status value. Use: on / off"
            )

        node = node_registry.get_node_by_id(node_id)
        if node is None:
            logging.warning(f"[Status] Unknown node_id '{node_id}'")
            return aiocoap.Message(
                code=aiocoap.NOT_FOUND,
                payload=f"Node '{node_id}' not registered".encode()
            )

        ip   = node["ip"]
        port = int(node.get("port", 5683))

        logging.info(
            f"[Status] Forwarding command → node '{node_id}' "
            f"({ip}:{port})  status={status}"
        )

        try:
            reply = await coap_client.set_status(ip, port, status)
            return aiocoap.Message(
                code=aiocoap.CHANGED, payload=reply.encode()
            )
        except ValueError as e:
            return aiocoap.Message(code=aiocoap.BAD_REQUEST, payload=str(e).encode())
        except Exception as e:
            logging.error(f"[Status] Failed to reach node '{node_id}': {e}")
            return aiocoap.Message(
                code=aiocoap.SERVICE_UNAVAILABLE,
                payload=f"Could not reach node: {e}".encode()
            )


def create_coap_site():
    """Build the CoAP resource tree."""
    root = resource.Site()
    root.add_resource(['telemetry'],          TelemetryResource())
    root.add_resource(['register'],           RegisterResource())
    root.add_resource(['unregister'],         UnregisterResource())
    root.add_resource(['actuators', 'leds'],  LedControlResource())
    root.add_resource(['actuators', 'status'], StatusControlResource())
    return root
