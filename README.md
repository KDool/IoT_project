# Autonomous Energy Management for a Remote Environmental Monitoring Station

**University of Pisa — Internet of Things (A.Y. 2025/2026)**
Professors: Giuseppe Anastasi, Francesca Righetti, Carlo Vallati
Students: Pietro Gemelli, Van Khai Do

Full report: [`IoT_Report.pdf`](IoT_Report.pdf)

---

## 1. Project Description

This project designs and implements an IoT energy-management system for an **unmanned, off-grid
environmental monitoring station**: no grid connection, no continuous human supervision, and only an
unreliable, low-bandwidth radio/satellite uplink back to a research center. Under these constraints the
station has to make short-term operational decisions on its own, without waiting for confirmation from
the cloud.

The system combines:

- **Renewable-first energy balancing** — solar and wind feed a battery that buffers short-term
  surplus/deficit.
- **On-device battery protection** — the battery firmware autonomously refuses unsafe charging (state of
  charge ≥ 95%), independent of cloud connectivity.
- **Diesel as a last-resort backup** — dispatched only when renewables and battery reserve are both
  insufficient (SoC < 20%), with hysteresis to avoid rapid on/off cycling.
- **A network layer that degrades gracefully** — the cloud detects rising MQTT delay (congestion) and
  a node's unresponsiveness (failure), and reacts autonomously in both cases instead of letting telemetry
  collapse.
- **On-device fault detection (planned/ML)** — a lightweight decision-tree classifier (trained offline,
  exported to C via `m2cgen`) for local voltage/current fault detection on the producer nodes.

Built on **Contiki-NG / Cooja**, **CoAP** (registration + actuator control), **MQTT** (telemetry
streaming), **InfluxDB** (time-series storage), and **Grafana** (dashboards).

See [`IoT_Report.pdf`](IoT_Report.pdf) for the full use case, requirements, stress-test methodology, and
results.

---

## 2. System Architecture

```
 Solar Sensor   Wind Sensor   Diesel Sensor   Battery Sensor
 (CoAP+MQTT)    (CoAP+MQTT)   (CoAP+MQTT)     (CoAP only)
      \              |              |              /
       \_____________|______________|_____________/
                      |
              tunslip6 / Border Router  (6LoWPAN / RPL)
                      |
            ┌─────────┴─────────┐
            |                   |  MQTT
       CoAP |               Mosquitto broker
            |                   |
            └─────────┬─────────┘
                       |
            Cloud Application (Python)
          CoAP server/client + MQTT client
          (registration, energy balance,
           adaptive congestion & failure
           detection)
                       |
                   InfluxDB  ──────►  Grafana
```

### Nodes

| Node | Firmware | Protocols | Role |
|---|---|---|---|
| Solar / Wind / Diesel (producers) | `sensors/coap-mqtt-*-sensor/*.c` — share `coap-mqtt-sensor.c`, differentiated by `NODE_TYPE` | CoAP client/server + MQTT publisher | Samples simulated voltage/current, publishes telemetry, exposes `/actuators/leds`, `/actuators/status`, `/test/push`. Registers once at startup (`POST /register`); the cloud subscribes back via CoAP Observe. The diesel node starts OFF and simulates a 40 s warm-up before producing power. |
| Battery | `sensors/coap-mqtt-battery-sensor` | CoAP only (no MQTT loop) | Maintains `charged_capacity`/`max_capacity`, applies charge/discharge deltas via `/actuators/battery`, autonomously enforces the charge lock (95% lock / 75% unlock), with `/actuators/battery/override` for manual bypass. |
| Border router | `sensors/rpl-border-router` | 6LoWPAN/RPL ↔ `tunslip6` | Bridges the simulated wireless network to the host. |
| Cloud application | `cloud-application/cloud_app.py` | CoAP server/client + MQTT subscriber | Node registration/registry, InfluxDB persistence, the 5 s energy-balance loop (incl. diesel dispatch), the 10 s CoAP heartbeat/failure detection loop, and the adaptive MQTT sampling-rate (congestion) loop. |

**Protocols:** CoAP for registration and actuator control (sparse, request/response, needs explicit
confirmation — e.g. a battery rejecting a charge command); MQTT for telemetry streaming (frequent,
one-to-many, publish/subscribe).

### Repository layout

```
IoT_project/
├── sensors/                    Contiki-NG firmware (solar, wind, diesel, battery, border router)
├── cloud-application/          Python cloud app (CoAP + MQTT + InfluxDB)
├── infrastructure/             docker-compose for MySQL, InfluxDB, Grafana
├── tinyML/                     Decision-tree fault classifier, exported to C via m2cgen
├── logic/                      Architecture diagrams (drawio)
├── prod simulate.csc           Cooja simulation topology (4 producer/battery motes + border router)
└── IoT_Report.pdf              Full project report
```

---

## 3. How to Setup and Run

### 3.1 Prerequisites

- [Contiki-NG](https://github.com/contiki-ng/contiki-ng) — clone it **next to** this repository (the
  sensor Makefiles resolve it at `../../../contiki-ng`), plus its toolchain for `TARGET=cooja` or
  `TARGET=nrf52840 BOARD=dongle`.
- Java + Cooja (bundled with Contiki-NG) to run the network simulation, or physical nRF52840 dongles.
- Docker + Docker Compose (Compose v2) for InfluxDB/Grafana/MySQL.
- Python 3.10+.
- A local **MQTT broker** (e.g. Mosquitto) listening on `localhost:1883` — the sensors' `tunslip6` tunnel
  and the cloud app both expect the broker reachable at `fd00::1` / `localhost` respectively. On macOS:
  `brew install mosquitto && mosquitto -v`.

### 3.2 Start the infrastructure (InfluxDB + Grafana + MySQL)

```bash
cd infrastructure
docker compose up -d
```

This brings up:
- **InfluxDB** on `localhost:8086` (bucket `iot_des`, org `iot_org`) — the cloud app's actual telemetry
  store, wired to Grafana via `infrastructure/grafana/provisioning/datasources/influxdb.yaml`.
- **Grafana** on `http://localhost:3000` (`admin` / `adminpassword`) — dashboards auto-provisioned from
  `infrastructure/grafana/provisioning/dashboards/`.
- **MySQL** on `localhost:3306` (`iot_des` / `iot_user` / `iot_password`) — schema in `init.sql` for
  device/telemetry/network-metrics tables (provisioned for future use; the current cloud app persists to
  InfluxDB).

Stop with `docker compose down` (add `-v` to also wipe volumes).

### 3.3 Build and run the Contiki-NG network (Cooja)

1. Open `prod simulate.csc` in Cooja — it starts the border router plus solar/wind/diesel/battery motes.
2. Or build manually per node, e.g.:
   ```bash
   cd sensors/coap-mqtt-sensor
   make TARGET=cooja NODE_TYPE=solar
   # NODE_TYPE=wind | solar | diesel  (shared firmware, differentiated by macro)
   ```
   For real dongles: `make TARGET=nrf52840 BOARD=dongle NODE_TYPE=solar` (see
   [`sensors/README.md`](sensors/README.md)).
3. Build and start the border router, then bridge it to the host:
   ```bash
   cd sensors/rpl-border-router
   make TARGET=cooja connect-router-cooja   # or the platform-appropriate tunslip6 target
   ```
   This creates the `tun0` interface (`fd00::1`) that the cloud app and MQTT broker are reached through.

Per-node behaviour (publish interval, IPv6 endpoint of the cloud app, simulated V/I ranges, anomaly
injection rate) is tunable in each sensor's `project-conf.h`.

### 3.4 Run the cloud application

```bash
cd cloud-application
python3 -m venv env
source env/bin/activate        # Windows: .\env\Scripts\Activate.ps1
pip install -r requirements.txt
python cloud_app.py
```

Configuration (InfluxDB URL/token, MQTT broker, CoAP bind address) lives in
`cloud-application/configuration.json`. On startup the app:

- starts a CoAP server (`/register`, `/unregister`, `/telemetry`, `/actuators/*`),
- starts the MQTT subscriber thread,
- runs the energy-balance loop every 5 s (`BALANCE_INTERVAL_S`),
- runs the CoAP heartbeat/failure-detection loop every 10 s,
- runs the adaptive congestion-control loop every 5 s.

As sensor nodes boot and register, watch the logs for registration, heartbeat, and energy-balance events.
Grafana (`http://localhost:3000`) then visualises the InfluxDB telemetry live.

### 3.5 (Optional) Retrain the ML fault classifier

```bash
cd tinyML
python3 -m venv env && source env/bin/activate
pip install -r requirements.txt
jupyter notebook notebook.ipynb
```

The notebook trains a depth-capped decision tree on the Kaggle *Electrical Fault Detection and
Classification* dataset (`dataset/`) and exports it via `m2cgen` to
`sensors/coap-mqtt-sensor/detect_anomaly.h`, shared by all producer firmware.

---

## 4. Result

Full methodology, logs, and figures are in [`IoT_Report.pdf`](IoT_Report.pdf) (§5). Summary:

### Network congestion

- Stress-tested on Cooja and physical dongles at publish periods 5000/2000/1000/800 ms.
- Packet delivery ratio stays at 100% down to 1000 ms and only drops (79–89%) at 800 ms — still within the
  80% accepted-loss tolerance.
- Delay stays under 200 ms at ≥1000 ms but reaches 818–1006 ms at 800 ms on both platforms — an
  unambiguous signal, used as the adaptive-mechanism trigger (average delay over the last 5 samples
  > 400 ms).
- **Without adaptation** at 800 ms: delay grows to ~1006 ms and the MQTT connection eventually
  disconnects.
- **With adaptation**: the cloud detects the rising delay, commands the node (`PUT /actuators/sampling`)
  to fall back to a 5000 ms interval, and restores the learned baseline once delay recovers. The
  connection stays stable, with average delay settling around 600 ms instead of failing outright.

### Node failure

- Disabling a solar node mid-run (`prod_solar_0003`) is detected within one heartbeat cycle
  (10 s probe / 3 s timeout): the cloud logs the failed heartbeat, removes the node from the registry, and
  excludes its stale telemetry from the energy-balance loop.
- Renewable production visibly drops (e.g. ~922–937 W → ~370–412 W) after removal, confirming the
  energy balance correctly reflects the reduced active fleet rather than using stale readings.

### Energy balance and battery protection

- The battery firmware enforces its charge lock (rejects charge with CoAP 4.03 Forbidden at SoC ≥ 95%,
  resumes below 75%) entirely on-device, independent of cloud/uplink availability.
- Diesel is dispatched only when renewables can't cover load and SoC < 20%, and stopped once SoC
  recovers past 40% (hysteresis prevents rapid on/off cycling), minimising fuel-resupply trips.

### Limitations (see report §7 for details and future work)

- Non-persistent node registry (lost on cloud-app restart without a matching simulation restart).
- No de-duplication of CoAP Observe subscriptions on re-registration.
- Synthetic load is uncorrelated pseudo-random noise rather than a realistic time series.
- ML fault classifier is trained on a public dataset, not on data collected from this deployment.
