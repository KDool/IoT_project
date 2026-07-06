#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* ── Node type ────────────────────────────────────────────────────────────── */
/* Defines the sensor type used in node_id ("prod_solar_XXYY")
 * and in the "type" field of MQTT telemetry JSON. */
#define NODE_TYPE "solar"

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

/* ── Sensor simulation ranges (Solar ~600 W max) ─────────────────────────── */
/* Voltage: V_BASE + (rand % V_RANGE)   →  32–36 V  */
#define SENSOR_V_BASE   32
#define SENSOR_V_RANGE   5
/* Current: I_BASE + (rand % I_RANGE)   →  15–17 A  */
#define SENSOR_I_BASE   15
#define SENSOR_I_RANGE   3
/* Max P ≈ 36.9 × 17.9 ≈ 661 W  (nominal ceiling ~600 W) */

/* ── Logging ──────────────────────────────────────────────────────────────── */
#define LOG_LEVEL_APP LOG_LEVEL_INFO

#endif /* PROJECT_CONF_H_ */
