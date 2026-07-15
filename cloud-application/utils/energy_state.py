"""
utils/energy_state.py

Renewable-first energy balance with diesel dispatched only as an
emergency backup when the battery state of charge drops below a
critical threshold and renewable production alone cannot cover the load.
"""

import asyncio
import logging
import random
import time
from influxdb_client import Point
from utils import node_registry, coap_client
from utils.influxdb_connect import write_api, INFLUX_BUCKET

logger = logging.getLogger(__name__)

RENEWABLE_TYPES = {"solar", "wind"}   # continuous, non-dispatchable producers
DIESEL_TYPE = "diesel"               # dispatchable emergency backup

MAX_CHARGE_W = 2000.0
MAX_DISCHARGE_W = 3000.0
BALANCE_INTERVAL_S = 5

LOAD_TYPICAL_W = 2000.0
LOAD_MIN_W = 300.0
LOAD_MAX_W = 2000.0
LOAD_PEAK_PROBABILITY = 0.05
LOAD_PEAK_W = 3000.0

# --- Diesel dispatch thresholds (fraction of battery max_capacity) ---
DIESEL_DISPATCH_SOC = 0.20   # start diesel if SoC drops below this AND renewable deficit
DIESEL_RECOVER_SOC = 0.40    # stop diesel once SoC climbs back above this (hysteresis)

_latest_readings: dict[str, dict] = {}   # node_id -> {"type", "power_w", "ts"}
_diesel_dispatched: bool = False


def update_reading(payload: dict):
    """Called for every ingested telemetry payload (MQTT or CoAP), producers only."""
    node_id = payload.get("node_id")
    node_type = payload.get("type")
    if not node_id or node_type not in (RENEWABLE_TYPES | {DIESEL_TYPE}):
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


def _power_by_types(types: set[str], stale_after_s: float = 30.0) -> float:
    now = time.time()
    return float(sum(
        r["power_w"] for node_id, r in _latest_readings.items()
        if r["type"] in types
        and now - r["ts"] <= stale_after_s
        and node_registry.get_node_by_id(node_id) is not None
    ))


async def _get_battery_soc(battery_node: dict) -> float | None:
    try:
        reply = await asyncio.wait_for(
            coap_client.get_battery_state(
                battery_node["ip"], int(battery_node.get("port", 5683))
            ),
            timeout=3.0
        )
        if reply["max_capacity"] <= 0:
            return None
        return reply["charged_capacity"] / reply["max_capacity"]
    except asyncio.TimeoutError:
        logger.warning("[EnergyBalance] Battery state GET timed out — skipping this cycle.")
        return None
    except Exception as e:
        logger.error(f"[EnergyBalance] Failed to read battery state: {e}")
        return None

async def _update_diesel_dispatch(soc: float | None, renewable_surplus_w: float):
    global _diesel_dispatched

    logger.info(f"[DEBUG] All registered nodes: {node_registry.get_all_nodes()}")  # ← temporaneo

    diesel_node = next(
        (n for n in node_registry.get_all_nodes() if n.get("type") == DIESEL_TYPE),
        None,
    )
    logger.info(f"[DEBUG] diesel_node found: {diesel_node}")  # ← temporaneo
    if diesel_node is None:
        return

    if soc is None:
        return  # cannot make a safe dispatch decision without battery ground truth

    should_run = _diesel_dispatched

    if not _diesel_dispatched and soc < DIESEL_DISPATCH_SOC and renewable_surplus_w < 0:
        should_run = True
        logger.info(
            f"[EnergyBalance] SoC {soc*100:.0f}% below {DIESEL_DISPATCH_SOC*100:.0f}% "
            f"and renewable deficit {renewable_surplus_w:.1f}W — dispatching diesel backup."
        )
    elif _diesel_dispatched and soc > DIESEL_RECOVER_SOC:
        should_run = False
        logger.info(
            f"[EnergyBalance] SoC {soc*100:.0f}% above recovery threshold "
            f"{DIESEL_RECOVER_SOC*100:.0f}% — stopping diesel backup."
        )

    if should_run != _diesel_dispatched:
        try:
            await coap_client.set_status(
                diesel_node["ip"], int(diesel_node.get("port", 5683)),
                "on" if should_run else "off"
            )
            _diesel_dispatched = should_run
        except Exception as e:
            logger.error(f"[EnergyBalance] Failed to dispatch diesel: {e}")


async def balance_loop():
    while True:
        try:
            await asyncio.sleep(BALANCE_INTERVAL_S)

            renewable_w = _power_by_types(RENEWABLE_TYPES)
            diesel_w = _power_by_types({DIESEL_TYPE})
            load_w = _generate_load_w()

            renewable_surplus_w = renewable_w - load_w
            total_surplus_w = renewable_w + diesel_w - load_w

            battery_node = next(
                (n for n in node_registry.get_all_nodes() if n.get("type") == "battery"),
                None,
            )

            soc = await _get_battery_soc(battery_node) if battery_node else None
            await _update_diesel_dispatch(soc, renewable_surplus_w)

            delta_kwh = 0.0
            battery_reachable = False

            if battery_node is not None:
                if total_surplus_w > 0:
                    clamped_w, sign = min(total_surplus_w, MAX_CHARGE_W), 1
                elif total_surplus_w < 0:
                    clamped_w, sign = min(-total_surplus_w, MAX_DISCHARGE_W), -1
                else:
                    clamped_w, sign = 0.0, 0

                delta_kwh = sign * clamped_w * (BALANCE_INTERVAL_S / 3600.0) / 1000.0

                if delta_kwh != 0.0:
                    try:
                        await coap_client.adjust_battery(
                            battery_node["ip"], int(battery_node.get("port", 5683)), delta_kwh
                        )
                        battery_reachable = True
                    except coap_client.BatteryChargeLockedError:
                        logger.info("[EnergyBalance] Charge command rejected — battery SoC lock active.")
                        battery_reachable = True
                    except Exception as e:
                        logger.error(f"[EnergyBalance] Failed to update battery: {e}")
            else:
                logger.warning("[EnergyBalance] No battery node registered yet.")

            logger.info(
                f"[EnergyBalance] renewable={renewable_w:.1f}W  diesel={diesel_w:.1f}W  "
                f"load={load_w:.1f}W  soc={'n/a' if soc is None else f'{soc*100:.0f}%'}  "
                f"delta={delta_kwh:.5f}kWh  diesel_dispatched={_diesel_dispatched}"
            )

            point = (
                Point("energy_balance")
                .field("renewable_w", renewable_w)
                .field("diesel_w", diesel_w)
                .field("load_w", load_w)
                .field("surplus_w", total_surplus_w)
                .field("delta_kwh", delta_kwh)
                .field("battery_reachable", int(battery_reachable))
                .field("battery_soc", -1.0 if soc is None else soc)
                .field("diesel_dispatched", int(_diesel_dispatched))
            )
            write_api.write(bucket=INFLUX_BUCKET, record=point)

        except Exception:
            logger.exception("[EnergyBalance] Uncaught exception in balance_loop cycle")
