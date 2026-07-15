#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* ── Node type ────────────────────────────────────────────────────────────── */
#define NODE_TYPE "battery"

/* ── CoAP ─────────────────────────────────────────────────────────────────── */
#ifndef CLOUD_COAP_EP
#define CLOUD_COAP_EP "coap://[fd00::1]:5683"
#endif

#define COAP_MAX_CHUNK_SIZE 192

/* ── Battery simulation ─────────────────────────────────────────────────── */
#define BATTERY_MAX_CAPACITY 10.0  /* kWh */
#define BATTERY_START_CAPACITY 5.0 /* kWh */

/* ── Logging ──────────────────────────────────────────────────────────────── */
#define LOG_LEVEL_APP LOG_LEVEL_INFO

#endif /* PROJECT_CONF_H_ */
