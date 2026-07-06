/*
 * coap-mqtt-battery-sensor.c
 *
 * Standalone Contiki-NG firmware for the Battery Sensor.
 *
 * It provides:
 * 1. CoAP SERVER: Exposes /actuators/battery to receive charge/discharge values
 *                 and GET to return current capacity.
 * 2. CoAP CLIENT: Registers itself to the cloud on startup.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "contiki.h"
#include "contiki-net.h"

/* CoAP */
#include "coap-engine.h"
#include "coap-blocking-api.h"

/* Network helpers */
#include "net/routing/routing.h"
#include "net/ipv6/uip.h"
#include "net/ipv6/uip-ds6.h"
#include "net/ipv6/uiplib.h"

/* Timers */
#include "sys/etimer.h"
#include "sys/ctimer.h"

/* Logging */
#include "sys/log.h"
#define LOG_MODULE "BatterySensor"
#define LOG_LEVEL  LOG_LEVEL_INFO

/* Configurations */
#ifndef NODE_TYPE
#define NODE_TYPE "battery"
#endif

#ifndef CLOUD_COAP_EP
#define CLOUD_COAP_EP "coap://[fd00::1]:5683"
#endif
#define CLOUD_REGISTER_PATH "register"

#ifndef BATTERY_MAX_CAPACITY
#define BATTERY_MAX_CAPACITY 100.0
#endif
#ifndef BATTERY_START_CAPACITY
#define BATTERY_START_CAPACITY 50.0
#endif

#define REGISTER_DELAY (15 * CLOCK_SECOND)

/* ═══════════════════════════════════════════════════════════════════════════
 * STATE
 * ═══════════════════════════════════════════════════════════════════════════ */

static char node_ip_str[42];
static char node_id[32];

float max_capacity = BATTERY_MAX_CAPACITY;
float charged_capacity = BATTERY_START_CAPACITY;

/* Forward declarations */
static void get_node_ip(void);
static bool have_connectivity(void);

extern coap_resource_t res_battery;

/* ═══════════════════════════════════════════════════════════════════════════
 * PROCESS DECLARATIONS
 * ═══════════════════════════════════════════════════════════════════════════ */

PROCESS(coap_server_process,   "CoAP Server");
PROCESS(coap_register_process, "CoAP Register");

AUTOSTART_PROCESSES(&coap_server_process, &coap_register_process);

/* Helpers */
static bool have_connectivity(void)
{
  return (uip_ds6_get_global(ADDR_PREFERRED) != NULL &&
          uip_ds6_defrt_choose() != NULL);
}

static void get_node_ip(void)
{
  uip_ds6_addr_t *addr = uip_ds6_get_global(ADDR_PREFERRED);
  if(addr == NULL) {
    addr = uip_ds6_get_link_local(ADDR_PREFERRED);
  }
  if(addr != NULL) {
    uiplib_ipaddr_snprint(node_ip_str, sizeof(node_ip_str), &addr->ipaddr);
  } else {
    snprintf(node_ip_str, sizeof(node_ip_str), "unknown");
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
 * PROCESS 1: CoAP SERVER
 * ═══════════════════════════════════════════════════════════════════════════ */
PROCESS_THREAD(coap_server_process, ev, data)
{
  PROCESS_BEGIN();
  PROCESS_PAUSE();

  LOG_INFO("CoAP server starting...\n");
  coap_activate_resource(&res_battery, "actuators/battery");
  LOG_INFO("CoAP server ready: /actuators/battery is active.\n");

  while(1) {
    PROCESS_WAIT_EVENT();
  }

  PROCESS_END();
}

/* ═══════════════════════════════════════════════════════════════════════════
 * PROCESS 2: CoAP REGISTER
 * ═══════════════════════════════════════════════════════════════════════════ */
static coap_endpoint_t cloud_ep;
static coap_message_t  reg_request[1];

static void coap_reg_response_handler(coap_message_t *response)
{
  if(response == NULL) {
    LOG_WARN("[CoAP Register] Timed out\n");
    return;
  }
  const uint8_t *pl;
  int len = coap_get_payload(response, &pl);
  LOG_INFO("[CoAP Register] Cloud replied: %.*s\n", len, (char *)pl);
}

PROCESS_THREAD(coap_register_process, ev, data)
{
  static struct etimer t;
  PROCESS_BEGIN();

  snprintf(node_id, sizeof(node_id), "prod_" NODE_TYPE "_%02x%02x",
           linkaddr_node_addr.u8[6], linkaddr_node_addr.u8[7]);

  do {
    etimer_set(&t, REGISTER_DELAY);
    PROCESS_WAIT_UNTIL(etimer_expired(&t));
  } while(!have_connectivity());

  get_node_ip();

  static char payload[160];
  snprintf(payload, sizeof(payload),
    "{\"node_id\":\"%s\",\"ip\":\"%s\",\"port\":5683,"
    "\"type\":\"" NODE_TYPE "\",\"proto\":\"coap\"}",
    node_id, node_ip_str);

  coap_endpoint_parse(CLOUD_COAP_EP, strlen(CLOUD_COAP_EP), &cloud_ep);
  coap_init_message(reg_request, COAP_TYPE_CON, COAP_POST, 0);
  coap_set_header_uri_path(reg_request, CLOUD_REGISTER_PATH);
  coap_set_header_content_format(reg_request, APPLICATION_JSON);
  coap_set_payload(reg_request, (uint8_t *)payload, strlen(payload));

  LOG_INFO("[CoAP Register] Sending to %s\n", CLOUD_COAP_EP);
  COAP_BLOCKING_REQUEST(&cloud_ep, reg_request, coap_reg_response_handler);

  PROCESS_END();
}
