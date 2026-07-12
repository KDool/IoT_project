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

#define SOC_LOCK_THRESHOLD   0.95f   /* stop accepting charge above this SoC */
#define SOC_UNLOCK_THRESHOLD 0.75f   /* resume accepting charge below this SoC */

static bool charging_locked  = false;
static bool override_active  = false;  /* manual bypass, set via /actuators/battery/override */

/* ── /actuators/battery ──────────────────────────────────────────────── */
static void res_get_battery_handler(coap_message_t *request, coap_message_t *response,
                                    uint8_t *buffer, uint16_t preferred_size, int32_t *offset);
static void res_put_battery_handler(coap_message_t *request, coap_message_t *response,
                                    uint8_t *buffer, uint16_t preferred_size, int32_t *offset);

RESOURCE(res_battery,
         "title=\"Battery capacity update\";rt=\"Control\"",
         res_get_battery_handler,
         NULL,
         res_put_battery_handler,
         NULL);

static void
update_lock_state(void)
{
  float soc = charged_capacity / max_capacity;
  if(soc >= SOC_LOCK_THRESHOLD && !charging_locked) {
    charging_locked = true;
    LOG_INFO("[BMS] SoC %.0f%% >= 95%% — charging LOCKED\n", soc * 100);
  } else if(soc <= SOC_UNLOCK_THRESHOLD && charging_locked) {
    charging_locked = false;
    LOG_INFO("[BMS] SoC %.0f%% <= 75%% — charging UNLOCKED\n", soc * 100);
  }
}

static void
res_get_battery_handler(coap_message_t *request, coap_message_t *response,
                        uint8_t *buffer, uint16_t preferred_size, int32_t *offset)
{
  char payload[160];
  int c_int = (int)charged_capacity;
  int c_frac = (int)((charged_capacity - c_int) * 10.0);
  if(c_frac < 0) c_frac = -c_frac;
  int m_int = (int)max_capacity;
  int m_frac = (int)((max_capacity - m_int) * 10.0);
  if(m_frac < 0) m_frac = -m_frac;

  snprintf(payload, sizeof(payload),
           "{\"max_capacity\":%d.%d,\"charged_capacity\":%d.%d,\"charging_locked\":%s,\"override\":%s}",
           m_int, m_frac, c_int, c_frac,
           charging_locked ? "true" : "false",
           override_active ? "true" : "false");

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

  /* Autonomous refusal: charging (delta > 0) while locked and no override active */
  if(delta > 0.0f && charging_locked && !override_active) {
    LOG_INFO("[BMS] Charge command REJECTED (locked, SoC=%.0f%%)\n",
             (charged_capacity / max_capacity) * 100);
    coap_set_status_code(response, FORBIDDEN_4_03);
    coap_set_payload(response, (uint8_t *)"charging_locked", 15);
    return;
  }

  charged_capacity += delta;
  if(charged_capacity < 0.0) charged_capacity = 0.0;
  if(charged_capacity > max_capacity) charged_capacity = max_capacity;

  update_lock_state();

  LOG_INFO("[CoAP] Battery adjusted by %.4f. New capacity: %.4f / %.1f kWh (locked=%d)\n",
           delta, charged_capacity, max_capacity, charging_locked);

  coap_set_status_code(response, CHANGED_2_04);
  coap_set_payload(response, (uint8_t *)"updated", 7);
}

/* ── /actuators/battery/override — manual bypass toggle ────────────────── */
static void res_get_override_handler(coap_message_t *request, coap_message_t *response,
                                     uint8_t *buffer, uint16_t preferred_size, int32_t *offset);
static void res_put_override_handler(coap_message_t *request, coap_message_t *response,
                                     uint8_t *buffer, uint16_t preferred_size, int32_t *offset);

RESOURCE(res_battery_override,
         "title=\"Manual bypass of charge lock: GET or PUT body=on|off\";rt=\"Control\"",
         res_get_override_handler,
         NULL,
         res_put_override_handler,
         NULL);

static void
res_get_override_handler(coap_message_t *request, coap_message_t *response,
                         uint8_t *buffer, uint16_t preferred_size, int32_t *offset)
{
  const char *payload = override_active ? "on" : "off";
  coap_set_header_content_format(response, TEXT_PLAIN);
  coap_set_payload(response, (uint8_t *)payload, strlen(payload));
}

static void
res_put_override_handler(coap_message_t *request, coap_message_t *response,
                         uint8_t *buffer, uint16_t preferred_size, int32_t *offset)
{
  const uint8_t *payload_bytes = NULL;
  int len = coap_get_payload(request, &payload_bytes);

  if(len >= 2 && strncmp((const char *)payload_bytes, "on", 2) == 0) {
    override_active = true;
    LOG_INFO("[BMS] Manual override ACTIVATED — charge lock bypassed\n");
  } else if(len >= 3 && strncmp((const char *)payload_bytes, "off", 3) == 0) {
    override_active = false;
    LOG_INFO("[BMS] Manual override DEACTIVATED — charge lock enforced normally\n");
  } else {
    coap_set_status_code(response, BAD_REQUEST_4_00);
    coap_set_payload(response, (uint8_t *)"Invalid body: use on|off", 24);
    return;
  }

  coap_set_status_code(response, CHANGED_2_04);
  coap_set_payload(response, (uint8_t *)(override_active ? "on" : "off"),
                   override_active ? 2 : 3);
}