# Cloud Application

Python backend for the IoT Energy Monitoring project.
Receives telemetry from Contiki-NG sensor nodes via MQTT and CoAP,
stores data in InfluxDB, and exposes control endpoints for LED and status commands.

---

## Message Delay Measurement (`delay_ms`)

### Problem: No Real-Time Clock on Sensors

Contiki-NG nodes running in Cooja do not have a hardware Real-Time Clock (RTC)
and cannot run SNTP (Simple Network Time Protocol) in a simulated 6LoWPAN network.
The only time source available on the sensor is `clock_seconds()`, which returns
the number of seconds elapsed **since the node booted** (uptime), not the real
wall-clock Epoch time.

This means you cannot directly subtract `sent_ms` (sensor uptime) from
`received_ms` (cloud Epoch time) to get a meaningful delay — the two clocks
live on completely different timelines.

---

### Solution: Minimum-Gap Baseline

The approach used here is based on a well-known network measurement technique
that eliminates the unknown boot-time offset without requiring any clock
synchronisation between sensor and cloud.

#### The Math

For any MQTT packet, define the **gap**:

```
current_gap = received_ms - sensor_uptime_ms
```

Expanding what each term represents:

```
received_ms      = T_boot_real + sensor_uptime_ms + transit_ms
current_gap      = received_ms - sensor_uptime_ms
                 = T_boot_real + transit_ms
```

Where:
- `T_boot_real`      — real Epoch time when the sensor booted (unknown, fixed per node)
- `sensor_uptime_ms` — value of `sent_ms` in the MQTT payload (uptime in ms)
- `transit_ms`       — time the packet took to traverse the network (what we want)

Because `sensor_uptime_ms` cancels out, `current_gap` equals the fixed unknown
`T_boot_real` plus the variable `transit_ms`.

Taking the minimum over all packets received from the same node:

```
min_offset = min(current_gap) = T_boot_real + min(transit_ms)
```

Therefore:

```
delay_ms = current_gap - min_offset
         = (T_boot_real + transit_ms) - (T_boot_real + min_transit_ms)
         = transit_ms - min_transit_ms
```

`T_boot_real` cancels completely. `delay_ms` is the **extra transit time** this
packet experienced compared to the fastest packet ever seen from the same node.

#### Properties

| Property | Value |
|---|---|
| Always non-negative | ✅ guaranteed — `delay_ms >= 0` by definition |
| Clock sync required | ❌ none needed |
| Works with QoS 0 | ✅ |
| Self-calibrating | ✅ baseline updates when a faster packet arrives |

---

### Implementation

**`utils/mqtt_client.py` — `on_message`**

The arrival timestamp is captured **immediately** when paho-mqtt delivers the
packet, before any processing takes place. This prevents InfluxDB write latency
or other processing delays from inflating `delay_ms`.

```python
def on_message(client, userdata, msg):
    received_ms = int(time.time() * 1000)   # stamped at arrival, not at write
    payload = json.loads(msg.payload.decode('utf-8'))
    save_to_influxdb(payload, received_ms)
```

**`utils/influxdb_connect.py` — `save_to_influxdb`**

A per-node dictionary `_mqtt_offsets` stores the minimum gap seen so far for
each `node_id`. It is updated every time a faster packet arrives, so the baseline
converges to the true minimum network latency as the RPL tree stabilises.

```python
current_gap = received_ms - sensor_uptime_ms

if node_id not in _mqtt_offsets or current_gap < _mqtt_offsets[node_id]:
    _mqtt_offsets[node_id] = current_gap   # update baseline

delay_ms = current_gap - _mqtt_offsets[node_id]   # always >= 0
```

---

### Why Not Other Approaches?

| Method | Reason not used |
|---|---|
| SNTP on sensor | Not available in Cooja 6LoWPAN simulation |
| CoAP registration timestamp | CoAP uses UDP — registration packet can arrive late, permanently biasing the offset |
| First-packet offset | First packet may arrive during slow RPL convergence, making all later packets appear negative |
| MQTT v5 broker timestamp | Requires MQTT v5 on Contiki-NG (not supported) |
| Round-trip ping (RTT) | Heavyweight, measures a different path than MQTT telemetry |

---

### Interpreting `delay_ms` in Grafana

| Value | Meaning |
|---|---|
| `0 ms` | Packet arrived as fast as the best packet ever seen from this node |
| `50–200 ms` | Normal RPL routing jitter |
| `> 500 ms` | Network congestion, RPL re-routing, or channel collision |
| Sustained increase | Growing backlog — broker or network is overloaded |

---

### Simulating Congestion in Cooja

To observe `delay_ms` spikes in Grafana:

1. Set `MQTT_PUBLISH_INTERVAL_S 1` in `project-conf.h` to flood the channel.
2. Add more sensor motes in Cooja (6–10 nodes sharing the same radio channel).
3. In Cooja → Edit → Radio Medium (UDGM), lower TX/RX ratio below 100% to
   introduce random packet loss and retransmissions.
4. Move nodes far from the border router to force multi-hop RPL paths.
