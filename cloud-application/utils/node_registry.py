"""
utils/node_registry.py

In-memory registry of sensor nodes that have registered with the cloud.
All writes happen inside the asyncio event loop (from CoAP resource handlers),
so no explicit locking is needed.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

# node_id → {node_id, ip, port, type, proto}
_nodes: dict[str, dict] = {}

# Async callback invoked whenever a new node registers
_on_new_node = None


def configure(on_new_node_callback):
    """
    Set the async callback that fires when a sensor registers.
    cloud_app.py passes coap_client.register_with_sensor here.
    """
    global _on_new_node
    _on_new_node = on_new_node_callback


def add_node(node_info: dict):
    """Store node info and trigger the back-registration callback."""
    node_id = node_info.get("node_id") or node_info.get("ip", "unknown")
    _nodes[node_id] = node_info
    logger.info(
        f"[Registry] Node '{node_id}' added  IP={node_info.get('ip')}  "
        f"port={node_info.get('port', 5683)}  total={len(_nodes)}"
    )
    if _on_new_node:
        asyncio.create_task(_on_new_node(node_info))


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
