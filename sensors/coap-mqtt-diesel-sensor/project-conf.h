#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* ── Node type ────────────────────────────────────────────────────────────── */
#define NODE_TYPE "diesel"

/* ── Device boot state ────────────────────────────────────────────────────── */
/* Diesel generator is OFF by default — must be started explicitly */
#define SENSOR_DEFAULT_ON 0

/* ── Startup warm-up delay ────────────────────────────────────────────────── */
/* After receiving "on" via CoAP, the generator takes 40 s to reach
 * operating state.  During this window status = "STARTING", v/i = 0. */
#define SENSOR_STARTUP_DELAY_S 40

/* ── Sensor simulation ranges (Diesel 1–3.5 kW) ──────────────────────────── */
/* Voltage: 220–230 V AC  →  V_BASE=220, V_RANGE=11               */
#define SENSOR_V_BASE   220
#define SENSOR_V_RANGE   11
/* Current: 5–15 A        →  I_BASE=5,   I_RANGE=11               */
#define SENSOR_I_BASE     5
#define SENSOR_I_RANGE   11
/* Min P ≈ 220 × 5  = 1100 W ≈ 1.1 kW  ✓                         */
/* Max P ≈ 230 × 15 = 3450 W ≈ 3.5 kW  ✓                         */

/* ── CoAP ─────────────────────────────────────────────────────────────────── */
#ifndef CLOUD_COAP_EP
#define CLOUD_COAP_EP "coap://[fd00::1]:5683"
#endif

#define COAP_MAX_CHUNK_SIZE 192

/* ── MQTT ─────────────────────────────────────────────────────────────────── */
#define UIP_CONF_TCP 1

#define MQTT_CLIENT_CONF_BROKER_IP_ADDR   "fd00::1"
#define MQTT_CLIENT_CONF_SENSOR_PUB_TOPIC "iot/telemetry"
#define MQTT_CLIENT_CONF_SENSOR_SUB_TOPIC "iot/cmd/%s"

/* Publish interval in seconds — tune per sensor type for traffic testing */
#define MQTT_PUBLISH_INTERVAL_S 10

/* ── Logging ──────────────────────────────────────────────────────────────── */
#define LOG_LEVEL_APP LOG_LEVEL_INFO

#endif /* PROJECT_CONF_H_ */
