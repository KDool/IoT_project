#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* ── Node type ────────────────────────────────────────────────────────────── */
/* Defines the sensor type used in node_id ("prod_<type>_XXYY")
 * and in the "type" field of MQTT telemetry JSON.
 * Override at build time:  make TARGET=cooja NODE_TYPE=solar */
#ifndef NODE_TYPE
#define NODE_TYPE "wind"
#endif

/* ── CoAP ─────────────────────────────────────────────────────────────────── */
/* IPv6 address of the host running cloud_app.py.
 * With tunslip6 the tun0 address is typically fd00::1. */
#ifndef CLOUD_COAP_EP
#define CLOUD_COAP_EP "coap://[fd00::1]:5683"
#endif

/* Default COAP_MAX_CHUNK_SIZE is 64 bytes — too small for the registration
 * JSON payload (~104 bytes). Increase to 192 to avoid truncation. */
#define COAP_MAX_CHUNK_SIZE 192

/* ── MQTT ─────────────────────────────────────────────────────────────────── */
#define UIP_CONF_TCP 1

#define MQTT_CLIENT_CONF_BROKER_IP_ADDR   "fd00::1"
#define MQTT_CLIENT_CONF_SENSOR_PUB_TOPIC "iot/telemetry"
#define MQTT_CLIENT_CONF_SENSOR_SUB_TOPIC "iot/cmd/%s"

/* Publish interval in milliseconds — tune per sensor type for traffic testing */
#define MQTT_PUBLISH_INTERVAL_MS 5000

/* ── Sensor simulation ranges (Wind ~400 W max) ──────────────────────────── */
/* Voltage: V_BASE + (rand % V_RANGE)   →  22–24 V  */
#define SENSOR_V_BASE   22
#define SENSOR_V_RANGE   3
/* Current: I_BASE + (rand % I_RANGE)   →  15–17 A  */
#define SENSOR_I_BASE   15
#define SENSOR_I_RANGE   3
/* Max P ≈ 24.9 × 17.9 ≈ 446 W  (nominal ceiling ~400 W) */

/* ── Anomaly simulation ratio ────────────────────────────────────────────── */
/* Percentage of MQTT publishes that will carry an injected fault reading.
 * 5 = ~5% of payloads are anomalous.  Range: 0 (disabled) – 100 (always). */
#define ANOMALY_INJECT_PERCENT 0

/* ── Logging ──────────────────────────────────────────────────────────────── */
#define LOG_LEVEL_APP LOG_LEVEL_INFO

#endif /* PROJECT_CONF_H_ */
