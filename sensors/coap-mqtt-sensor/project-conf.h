#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

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

/* MQTT broker IPv6 address (same host as the cloud app) */
#define MQTT_CLIENT_CONF_BROKER_IP_ADDR "fd00::1"

/* Telemetry publish topic – consumed by cloud_app.py */
#define MQTT_CLIENT_CONF_SENSOR_PUB_TOPIC  "iot/telemetry"

/* Per-device command topic – cloud sends LED commands here */
#define MQTT_CLIENT_CONF_SENSOR_SUB_TOPIC  "iot/cmd/%s"

/* ── Logging ──────────────────────────────────────────────────────────────── */
#define LOG_LEVEL_APP LOG_LEVEL_INFO

#endif /* PROJECT_CONF_H_ */
