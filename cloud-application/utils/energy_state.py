"""
utils/energy_state.py
"""

import asyncio
import logging
import random
import time

from influxdb_client import Point
from utils import node_registry, coap_client
from utils.influxdb_connect import write_api, INFLUX_BUCKET

logger = logging.getLogger(__name__)

PRODUCER_TYPES = {"solar", "wind"}

MAX_CHARGE_W = 2000.0
MAX_DISCHARGE_W = 3000.0
BALANCE_INTERVAL_S = 5

LOAD_TYPICAL_W = 800.0
LOAD_MIN_W = 300.0
LOAD_MAX_W = 2000.0
LOAD_PEAK_PROBABILITY = 0.05
LOAD_PEAK_W = 3000.0

_latest_readings: dict[str, dict] = {}


def update_reading(payload: dict):
    node_id = payload.get("node_id")
    node_type = payload.get("type")
    if not node_id or node_type not in PRODUCER_TYPES:
        return
    try:
        power_w = float(payload.get("v", 0.0)) * float(payload.get("i", 0.0))
    except (TypeError, ValueError):
        return
    _latest_readings[node_id] = {"type": node_type, "power_w": power_w, "ts": time.time()}


def _generate_load_w() -> float:
    if random.random() < LOAD_PEAK_PROBABILITY:
        return random.uniform(LOAD_MAX_W, LOAD_PEAK_W)
    return random.uniform(LOAD_MIN_W, LOAD_TYPICAL_W)


def _total_producer_power(stale_after_s: float = 30.0) -> float:
    now = time.time()
    return sum(
        (r["power_w"] for r in _latest_readings.values()
         if now - r["ts"] <= stale_after_s),
        0.0  # start=0.0 ensures sum() always returns float, even when empty
    )


async def balance_loop():
    while True:
        await asyncio.sleep(BALANCE_INTERVAL_S)

        producer_w = _total_producer_power()
        load_w = _generate_load_w()
        surplus_w = producer_w - load_w

        battery_node = next(
            (n for n in node_registry.get_all_nodes() if n.get("type") == "battery"),
            None,
        )

        delta_kwh = 0.0
        battery_reachable = False

        if battery_node is not None:
            if surplus_w > 0:
                clamped_w, sign = min(surplus_w, MAX_CHARGE_W), 1
            elif surplus_w < 0:
                clamped_w, sign = min(-surplus_w, MAX_DISCHARGE_W), -1
            else:
                clamped_w, sign = 0.0, 0

            delta_kwh = sign * clamped_w * (BALANCE_INTERVAL_S / 3600.0) / 1000.0

            if delta_kwh != 0.0:
                try:
                    await coap_client.adjust_battery(
                        battery_node["ip"], int(battery_node.get("port", 5683)), delta_kwh
                    )
                    battery_reachable = True
                except Exception as e:
                    logger.error(f"[EnergyBalance] Failed to update battery: {e}")
        else:
            logger.warning("[EnergyBalance] No battery node registered yet — skipping charge/discharge.")

        logger.info(
            f"[EnergyBalance] producer={producer_w:.1f}W  load={load_w:.1f}W  "
            f"surplus={surplus_w:.1f}W  delta={delta_kwh:.5f}kWh"
        )

        point = (
            Point("energy_balance")
            .field("producer_w", float(producer_w))
            .field("load_w", float(load_w))
            .field("surplus_w", float(surplus_w))
            .field("delta_kwh", float(delta_kwh))
            .field("battery_reachable", int(battery_reachable))
        )
        write_api.write(bucket=INFLUX_BUCKET, record=point)