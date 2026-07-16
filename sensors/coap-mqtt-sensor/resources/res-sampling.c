/*
 * res-sampling.c
 *
 * CoAP resource: actuators/sampling
 *
 * Allows the cloud to read and update the sensor publish interval at runtime.
 *
 * GET response: current interval in milliseconds
 * PUT body:     integer interval in milliseconds, e.g. "15000"
 */

#include "contiki.h"
#include "coap-engine.h"

#include <stdio.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "sys/log.h"
#define LOG_MODULE "res-sampling"
#define LOG_LEVEL  LOG_LEVEL_INFO

extern uint32_t get_publish_interval_ms(void);
extern void set_publish_interval_ms(uint32_t interval_ms);

static void res_get_handler(coap_message_t *req, coap_message_t *resp,
                            uint8_t *buf, uint16_t preferred_size,
                            int32_t *offset);
static void res_put_handler(coap_message_t *req, coap_message_t *resp,
                            uint8_t *buf, uint16_t preferred_size,
                            int32_t *offset);

RESOURCE(res_sampling,
         "title=\"Sampling interval control: GET or PUT body=<interval_ms>\";rt=\"Control\"",
         res_get_handler,
         NULL,
         res_put_handler,
         NULL);

static void
res_get_handler(coap_message_t *request, coap_message_t *response,
                uint8_t *buffer, uint16_t preferred_size, int32_t *offset)
{
  char payload[32];
  unsigned long interval_ms = (unsigned long)get_publish_interval_ms();

  coap_set_header_content_format(response, TEXT_PLAIN);
  snprintf(payload, sizeof(payload), "%lu", interval_ms);
  coap_set_payload(response, (uint8_t *)payload, strlen(payload));
}

static void
res_put_handler(coap_message_t *request, coap_message_t *response,
                uint8_t *buffer, uint16_t preferred_size, int32_t *offset)
{
  const uint8_t *payload_bytes = NULL;
  int len = coap_get_payload(request, &payload_bytes);

  if(len <= 0 || payload_bytes == NULL) {
    coap_set_status_code(response, BAD_REQUEST_4_00);
    coap_set_payload(response, (uint8_t *)"Missing body: interval_ms", 25);
    return;
  }

  char tmp[32];
  size_t copy_len = (size_t)len;
  if(copy_len >= sizeof(tmp)) {
    copy_len = sizeof(tmp) - 1;
  }
  memcpy(tmp, payload_bytes, copy_len);
  tmp[copy_len] = '\0';

  char *endptr = NULL;
  unsigned long interval_ms = strtoul(tmp, &endptr, 10);
  if(endptr == tmp || *endptr != '\0' || interval_ms < 1UL || interval_ms > 60000UL) {
    coap_set_status_code(response, BAD_REQUEST_4_00);
    coap_set_payload(response, (uint8_t *)"Invalid interval: use 1..60000", 30);
    return;
  }

  set_publish_interval_ms((uint32_t)interval_ms);

  LOG_INFO("[Sampling] Interval updated via CoAP PUT to %lu ms\n", interval_ms);
  coap_set_status_code(response, CHANGED_2_04);
  coap_set_payload(response, (uint8_t *)tmp, strlen(tmp));
}
