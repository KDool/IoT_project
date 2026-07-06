/*
 * res-status.c
 *
 * CoAP resource: actuators/status
 *
 * Allows the cloud application to PUT "on" or "off" to toggle the logical
 * device status (device_on flag).  The current status is also readable
 * via GET.  The MQTT publish loop reflects this flag in the "status" field
 * of the telemetry JSON.
 *
 * PUT body:  "on"  →  device_on = true
 *            "off" →  device_on = false
 *
 * GET response:  "on"  or  "off"
 */

#include "contiki.h"
#include "coap-engine.h"

#include <string.h>
#include <stdbool.h>

#include "sys/log.h"
#define LOG_MODULE "res-status"
#define LOG_LEVEL  LOG_LEVEL_INFO

/* Defined in coap-mqtt-sensor.c — shared device status flag */
extern bool device_on;

/* ── Forward declarations ────────────────────────────────────────────────── */
static void res_get_handler(coap_message_t *req, coap_message_t *resp,
                            uint8_t *buf, uint16_t preferred_size,
                            int32_t *offset);
static void res_put_handler(coap_message_t *req, coap_message_t *resp,
                            uint8_t *buf, uint16_t preferred_size,
                            int32_t *offset);

/* ── Resource declaration ────────────────────────────────────────────────── */
RESOURCE(res_status,
         "title=\"Device status: GET or PUT body=on|off\";rt=\"Control\"",
         res_get_handler,   /* GET  */
         NULL,              /* POST */
         res_put_handler,   /* PUT  */
         NULL);             /* DELETE */

/* ── GET: return current status ─────────────────────────────────────────── */
static void
res_get_handler(coap_message_t *request, coap_message_t *response,
                uint8_t *buffer, uint16_t preferred_size, int32_t *offset)
{
  const char *payload = device_on ? "on" : "off";
  coap_set_header_content_format(response, TEXT_PLAIN);
  coap_set_payload(response, (uint8_t *)payload, strlen(payload));
}

/* ── PUT: change device status ──────────────────────────────────────────── */
static void
res_put_handler(coap_message_t *request, coap_message_t *response,
                uint8_t *buffer, uint16_t preferred_size, int32_t *offset)
{
  const uint8_t *payload_bytes = NULL;
  int len = coap_get_payload(request, &payload_bytes);

  if(len <= 0 || payload_bytes == NULL) {
    coap_set_status_code(response, BAD_REQUEST_4_00);
    coap_set_payload(response, (uint8_t *)"Missing body: on|off", 20);
    return;
  }

  if(len >= 3 && strncmp((const char *)payload_bytes, "off", 3) == 0) {
    device_on = false;
    LOG_INFO("[Status] Device turned OFF via CoAP PUT\n");
    coap_set_status_code(response, CHANGED_2_04);
    coap_set_payload(response, (uint8_t *)"off", 3);
  } else if(len >= 2 && strncmp((const char *)payload_bytes, "on", 2) == 0) {
    device_on = true;
    LOG_INFO("[Status] Device turned ON via CoAP PUT\n");
    coap_set_status_code(response, CHANGED_2_04);
    coap_set_payload(response, (uint8_t *)"on", 2);
  } else {
    coap_set_status_code(response, BAD_REQUEST_4_00);
    coap_set_payload(response, (uint8_t *)"Invalid body: use on|off", 24);
  }
}
