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

static void
format_fixed_4(char *buf, size_t buf_len, float value)
{
  long scaled = (long)(value * 10000.0f + (value >= 0.0f ? 0.5f : -0.5f));
  long whole = scaled / 10000L;
  long frac = scaled % 10000L;

  if(frac < 0) {
    frac = -frac;
  }

  snprintf(buf, buf_len, "%ld.%04ld", whole, frac);
}

static void
format_fixed_1(char *buf, size_t buf_len, float value)
{
  long scaled = (long)(value * 10.0f + (value >= 0.0f ? 0.5f : -0.5f));
  long whole = scaled / 10L;
  long frac = scaled % 10L;

  if(frac < 0) {
    frac = -frac;
  }

  snprintf(buf, buf_len, "%ld.%ld", whole, frac);
}

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
  char soc_str[16];

  snprintf(soc_str, sizeof(soc_str), "%ld", (long)(soc * 100.0f + 0.5f));

  if(soc >= SOC_LOCK_THRESHOLD && !charging_locked) {
    charging_locked = true;
    LOG_INFO("[BMS] SoC %s%% >= 95%% — charging LOCKED\n", soc_str);
  } else if(soc <= SOC_UNLOCK_THRESHOLD && charging_locked) {
    charging_locked = false;
    LOG_INFO("[BMS] SoC %s%% <= 75%% — charging UNLOCKED\n", soc_str);
  }
}

static void
res_get_battery_handler(coap_message_t *request, coap_message_t *response,
                        uint8_t *buffer, uint16_t preferred_size, int32_t *offset)
{
  char payload[160];
  char charged_str[16];
  char max_str[16];

  format_fixed_1(max_str, sizeof(max_str), max_capacity);
  format_fixed_1(charged_str, sizeof(charged_str), charged_capacity);

  snprintf(payload, sizeof(payload),
           "{\"max_capacity\":%s,\"charged_capacity\":%s,\"charging_locked\":%s,\"override\":%s}",
           max_str, charged_str,
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
    {
      char soc_str[16];
      float soc = charged_capacity / max_capacity;

      snprintf(soc_str, sizeof(soc_str), "%ld", (long)(soc * 100.0f + 0.5f));
      LOG_INFO("[BMS] Charge command REJECTED (locked, SoC=%s%%)\n", soc_str);
    }
    coap_set_status_code(response, FORBIDDEN_4_03);
    coap_set_payload(response, (uint8_t *)"charging_locked", 15);
    return;
  }

  charged_capacity += delta;
  if(charged_capacity < 0.0) charged_capacity = 0.0;
  if(charged_capacity > max_capacity) charged_capacity = max_capacity;

  update_lock_state();

  {
    char delta_str[16];
    char charged_str[16];
    char max_str[16];

    format_fixed_4(delta_str, sizeof(delta_str), delta);
    format_fixed_4(charged_str, sizeof(charged_str), charged_capacity);
    format_fixed_1(max_str, sizeof(max_str), max_capacity);

    LOG_INFO("[CoAP] Battery adjusted by %s. New capacity: %s / %s kWh (locked=%d)\n",
             delta_str, charged_str, max_str, charging_locked);
  }

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
