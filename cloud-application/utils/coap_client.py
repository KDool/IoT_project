"""
utils/coap_client.py

CoAP client used by the cloud application to:
  1. Register with each sensor node by subscribing (GET Observe:0) to test/push.
     This is the cloud-side "register with sensor" step — the sensor then pushes
     periodic notifications to the cloud automatically.
  2. Send LED control commands to any registered sensor node by IP address.

set_protocol() must be called once at startup with a shared aiocoap.Context.
register_with_sensor() is wired as the node_registry callback so it fires
automatically when a sensor POSTs to /register on the cloud server.
"""

import asyncio
import logging
import json
import aiocoap

logger = logging.getLogger(__name__)

# Shared CoAP context — set once at startup by cloud_app.py
_protocol: aiocoap.Context | None = None

COLOR_MAP = {
    "red":   "r",
    "green": "g",
    "blue":  "b",
    "r": "r",
    "g": "g",
    "b": "b",
}


def set_protocol(protocol: aiocoap.Context):
    """Provide the shared aiocoap context used for all outgoing requests."""
    global _protocol
    _protocol = protocol
    logger.info("[CoAP Client] Protocol context ready.")


def _make_uri(ip: str, port: int, path: str) -> str:
    """Build a coap:// URI, wrapping bare IPv6 addresses in brackets."""
    addr = f"[{ip}]" if ":" in ip and not ip.startswith("[") else ip
    return f"coap://{addr}:{port}/{path}"

class BatteryChargeLockedError(Exception):
    """Raised when the battery firmware refuses a charge command (SoC lock active)."""
    pass


async def adjust_battery(ip: str, port: int, delta_kwh: float) -> str:
    """
    PUT coap://<battery>/actuators/battery  body: raw float (kWh delta)
    NOTE: unlike set_led/set_status, res-battery.c expects a plain
    text float, not JSON — see res_put_battery_handler().

    Raises BatteryChargeLockedError if the firmware rejects the command
    (4.03 Forbidden — autonomous SoC lock active, no manual override).
    """
    if not _protocol:
        raise RuntimeError("[CoAP Client] Protocol not set. Call set_protocol() first.")

    uri = _make_uri(ip, port, "actuators/battery")
    payload = f"{delta_kwh:.5f}".encode()

    request = aiocoap.Message(code=aiocoap.PUT, uri=uri, payload=payload)
    response = await _protocol.request(request).response

    reply = response.payload.decode()

    if response.code == aiocoap.FORBIDDEN:
        raise BatteryChargeLockedError(reply)

    if not response.code.is_successful():
        raise RuntimeError(f"Unexpected CoAP response ({response.code}): {reply}")

    return reply
# ──────────────────────────────────────────────────────────────────────────────
# Cloud → Sensor: Registration via CoAP Observe
# ──────────────────────────────────────────────────────────────────────────────
async def set_battery_override(ip: str, port: int, enabled: bool) -> str:

    if not _protocol:
        raise RuntimeError("[CoAP Client] Protocol not set. Call set_protocol() first.")

    uri = _make_uri(ip, port, "actuators/battery/override")
    payload = b"on" if enabled else b"off"

    request = aiocoap.Message(code=aiocoap.PUT, uri=uri, payload=payload)
    response = await _protocol.request(request).response
    return response.payload.decode()

async def register_with_sensor(node_info: dict):
    """
    Called automatically (via node_registry callback) when a sensor registers.

    The cloud subscribes (GET Observe:0) to the sensor's test/push resource.
    This IS the cloud-side registration — the sensor adds the cloud to its
    observer list and will push periodic EVENT notifications from that point on.
    """
    if not _protocol:
        logger.error("[CoAP Client] Protocol not set. Call set_protocol() first.")
        return

    ip      = node_info.get("ip")
    port    = int(node_info.get("port", 5683))
    node_id = node_info.get("node_id", ip)
    uri     = _make_uri(ip, port, "test/push")

    logger.info(f"[CoAP Client] Registering with sensor '{node_id}' → Observe GET {uri}")

    request = aiocoap.Message(code=aiocoap.GET, uri=uri, observe=0)
    try:
        observation = _protocol.request(request)
        first = await observation.response
        logger.info(
            f"[CoAP Client] Subscribed to '{node_id}' ({first.code}): "
            f"{first.payload.decode()}"
        )
        # Keep listening for push notifications in the background
        asyncio.create_task(_listen_push(node_id, observation))
    except Exception as e:
        logger.error(f"[CoAP Client] Failed to register with '{node_id}': {e}")


async def _listen_push(node_id: str, observation):
    """Background task: log all periodic push notifications from a sensor."""
    try:
        async for response in observation.observation:
            logger.info(
                f"[CoAP Client] Push from '{node_id}': {response.payload.decode()}"
            )
    except Exception as e:
        logger.warning(f"[CoAP Client] Observation for '{node_id}' ended: {e}")

async def get_battery_state(ip: str, port: int) -> dict:
    """
    GET coap://<battery>/actuators/battery
    Returns {"max_capacity": float, "charged_capacity": float,
             "charging_locked": bool, "override": bool}
    """
    if not _protocol:
        raise RuntimeError("[CoAP Client] Protocol not set. Call set_protocol() first.")

    uri = _make_uri(ip, port, "actuators/battery")
    request = aiocoap.Message(code=aiocoap.GET, uri=uri)
    response = await _protocol.request(request).response

    if not response.code.is_successful():
        raise RuntimeError(f"Unexpected CoAP response ({response.code})")

    return json.loads(response.payload.decode())
# ──────────────────────────────────────────────────────────────────────────────
# Cloud → Sensor: LED Control
# ──────────────────────────────────────────────────────────────────────────────

async def set_led(ip: str, port: int, color: str, mode: str) -> str:
    """
    Send PUT coap://<ip>:<port>/actuators/leds?color=<r|g|b>  body: mode=on|off
    Matches the interface of res-leds.c on the Contiki-NG node.
    Returns the sensor's reply string.
    """
    if not _protocol:
        raise RuntimeError("[CoAP Client] Protocol not set. Call set_protocol() first.")

    color_code = COLOR_MAP.get(color.lower())
    if not color_code:
        raise ValueError(f"Invalid color '{color}'. Use: red / green / blue")
    if mode.lower() not in ("on", "off"):
        raise ValueError(f"Invalid mode '{mode}'. Use: on / off")

    uri     = _make_uri(ip, port, f"actuators/leds?color={color_code}")
    payload = f"mode={mode.lower()}".encode()

    logger.info(f"[CoAP Client] → PUT {uri}  body: {payload.decode()}")
    request  = aiocoap.Message(code=aiocoap.PUT, uri=uri, payload=payload)
    response = await _protocol.request(request).response
    reply    = response.payload.decode()
    logger.info(f"[CoAP Client] ← Sensor replied ({response.code}): {reply}")
    return reply


# ──────────────────────────────────────────────────────────────────────────────
# Cloud → Sensor: Status Control
# ──────────────────────────────────────────────────────────────────────────────

async def set_status(ip: str, port: int, status: str) -> str:
    """
    Send PUT coap://<ip>:<port>/actuators/status  body: on|off
    Matches the interface of res-status.c on the Contiki-NG node.
    The sensor will update its device_on flag and reflect the new status
    in all subsequent MQTT telemetry publishes.
    Returns the sensor's reply string.
    """
    if not _protocol:
        raise RuntimeError("[CoAP Client] Protocol not set. Call set_protocol() first.")

    status_val = status.lower()
    if status_val not in ("on", "off"):
        raise ValueError(f"Invalid status '{status}'. Use: on / off")

    uri     = _make_uri(ip, port, "actuators/status")
    payload = status_val.encode()

    logger.info(f"[CoAP Client] → PUT {uri}  body: {payload.decode()}")
    request  = aiocoap.Message(code=aiocoap.PUT, uri=uri, payload=payload)
    response = await _protocol.request(request).response
    reply    = response.payload.decode()
    logger.info(f"[CoAP Client] ← Sensor replied ({response.code}): {reply}")
    return reply
