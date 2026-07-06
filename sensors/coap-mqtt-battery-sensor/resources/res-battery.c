/*
 * res-battery.c
 *
 * CoAP resource: /actuators/battery
 */

#include "contiki.h"
#include "coap-engine.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

#include "sys/log.h"
#define LOG_MODULE "BatteryResource"
#define LOG_LEVEL  LOG_LEVEL_INFO

extern float max_capacity;
extern float charged_capacity;

/* Forward declarations */
static void res_get_battery_handler(coap_message_t *request, coap_message_t *response,
                                    uint8_t *buffer, uint16_t preferred_size, int32_t *offset);
static void res_put_battery_handler(coap_message_t *request, coap_message_t *response,
                                    uint8_t *buffer, uint16_t preferred_size, int32_t *offset);

RESOURCE(res_battery,
         "title=\"Battery capacity update\";rt=\"Control\"",
         res_get_battery_handler,  /* GET */
         NULL,                     /* POST */
         res_put_battery_handler,  /* PUT */
         NULL);                    /* DELETE */

static void
res_get_battery_handler(coap_message_t *request, coap_message_t *response,
                        uint8_t *buffer, uint16_t preferred_size, int32_t *offset)
{
  char payload[128];
  
  int c_int = (int)charged_capacity;
  int c_frac = (int)((charged_capacity - c_int) * 10.0);
  if(c_frac < 0) c_frac = -c_frac;

  int m_int = (int)max_capacity;
  int m_frac = (int)((max_capacity - m_int) * 10.0);
  if(m_frac < 0) m_frac = -m_frac;

  snprintf(payload, sizeof(payload),
           "{\"max_capacity\":%d.%d,\"charged_capacity\":%d.%d}",
           m_int, m_frac, c_int, c_frac);

  coap_set_header_content_format(response, APPLICATION_JSON);
  coap_set_payload(response, (uint8_t *)payload, strlen(payload));
}

static void
res_put_battery_handler(coap_message_t *request, coap_message_t *response,
                        uint8_t *buffer, uint16_t preferred_size, int32_t *offset)
{
  const uint8_t *payload_bytes = NULL;
  int len = coap_get_payload(request, &payload_bytes);

  if(len <= 0 || payload_bytes == NULL) {
    coap_set_status_code(response, BAD_REQUEST_4_00);
    return;
  }

  char payload_str[32];
  int cp_len = len < sizeof(payload_str) - 1 ? len : sizeof(payload_str) - 1;
  memcpy(payload_str, payload_bytes, cp_len);
  payload_str[cp_len] = '\0';

  float delta = atof(payload_str);
  charged_capacity += delta;

  if(charged_capacity < 0.0) charged_capacity = 0.0;
  if(charged_capacity > max_capacity) charged_capacity = max_capacity;

  LOG_INFO("[CoAP] Battery adjusted by %.1f. New capacity: %.1f / %.1f kWh\n", 
           delta, charged_capacity, max_capacity);

  coap_set_status_code(response, CHANGED_2_04);
  coap_set_payload(response, (uint8_t *)"updated", 7);
}