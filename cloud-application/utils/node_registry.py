"""
utils/node_registry.py

In-memory registry of sensor nodes that have registered with the cloud.
All writes happen inside the asyncio event loop (from CoAP resource handlers),
so no explicit locking is needed.
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

# node_id → {node_id, ip, port, type, proto}
_nodes: dict[str, dict] = {}

# Async callback invoked whenever a new node registers
_on_new_node = None
_event_loop: asyncio.AbstractEventLoop | None = None


def configure(on_new_node_callback, event_loop: asyncio.AbstractEventLoop | None = None):
    """
    Set the async callback that fires when a sensor registers.
    cloud_app.py passes coap_client.register_with_sensor here.
    """
    global _on_new_node, _event_loop
    _on_new_node = on_new_node_callback
    _event_loop = event_loop


def _schedule_new_node_callback(node_info: dict):
    if _on_new_node is None:
        return

    coro = _on_new_node(node_info)
    if _event_loop is not None and _event_loop.is_running():
        asyncio.run_coroutine_threadsafe(coro, _event_loop)
        return

    try:
        asyncio.create_task(coro)
    except RuntimeError:
        logger.warning(
            f"[Registry] Could not schedule back-registration for node '{node_info.get('node_id')}' "
            "because no running event loop is available."
        )


def add_node(node_info: dict):
    """Store node info and trigger the back-registration callback."""
    node_id = node_info.get("node_id") or node_info.get("ip", "unknown")
    stored = {
        **node_info,
        "last_seen_ms": int(time.time() * 1000),
    }
    _nodes[node_id] = stored
    logger.info(
        f"[Registry] Node '{node_id}' added  IP={stored.get('ip')}  "
        f"port={stored.get('port', 5683)}  total={len(_nodes)}"
    )
    _schedule_new_node_callback(stored)


def update_heartbeat(payload: dict, received_ms: int | None = None):
    """Refresh last_seen when telemetry arrives. Re-add node if needed."""
    node_id = payload.get("node_id")
    if not node_id:
        return

    if received_ms is None:
        received_ms = int(time.time() * 1000)

    node = _nodes.get(node_id)
    if node is None:
        add_node(payload)
        node = _nodes.get(node_id)
        if node is None:
            return

    node["last_seen_ms"] = received_ms


def get_expired_nodes(timeout_ms: int, now_ms: int | None = None) -> list[dict]:
    """Return nodes that have not been seen within timeout_ms."""
    if now_ms is None:
        now_ms = int(time.time() * 1000)

    expired = []
    for node in _nodes.values():
        last_seen_ms = int(node.get("last_seen_ms", 0))
        if last_seen_ms and (now_ms - last_seen_ms) > timeout_ms:
            expired.append(node)
    return expired


def remove_node(node_id: str):
    if node_id in _nodes:
        del _nodes[node_id]
        logger.info(f"[Registry] Node '{node_id}' removed.")


def get_all_nodes() -> list[dict]:
    return list(_nodes.values())


def get_node_by_id(node_id: str) -> dict | None:
    return _nodes.get(node_id)


def get_node_by_ip(ip: str) -> dict | None:
    for node in _nodes.values():
        if node.get("ip") == ip:
            return node
    return None
