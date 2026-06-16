#include "contiki.h"
#include "net/routing/routing.h"
#include "mqtt.h"
#include "mqtt-prop.h"
#include "net/ipv6/uip.h"
#include "net/ipv6/uip-icmp6.h"
#include "net/ipv6/sicslowpan.h"
#include "sys/etimer.h"
#include "sys/ctimer.h"
#include "lib/sensors.h"
#include "dev/button-hal.h"
#include "dev/leds.h"
#include "os/sys/log.h"
#include "mqtt-client.h"

#include <string.h>
#include <strings.h>
#include <stdarg.h>

#define LOG_MODULE "mqtt-wind"
#define LOG_LEVEL LOG_LEVEL_INFO

/* MQTT broker address. Ignored in Watson mode */
#ifdef MQTT_CLIENT_CONF_BROKER_IP_ADDR
#define MQTT_CLIENT_BROKER_IP_ADDR MQTT_CLIENT_CONF_BROKER_IP_ADDR
#else
#define MQTT_CLIENT_BROKER_IP_ADDR "fd00::1"
#endif 

#define MQTT_BROKER_PORT    1883

/* Sensor publish topic - can be overridden in project-conf.h */
#ifdef MQTT_CLIENT_CONF_SENSOR_PUB_TOPIC
#define SENSOR_PUB_TOPIC MQTT_CLIENT_CONF_SENSOR_PUB_TOPIC
#else
#define SENSOR_PUB_TOPIC "iot/telemetry"
#endif

/* Sensor subscribe topic pattern - %s will be replaced with client_id */
#ifdef MQTT_CLIENT_CONF_SENSOR_SUB_TOPIC
#define SENSOR_SUB_TOPIC MQTT_CLIENT_CONF_SENSOR_SUB_TOPIC
#else
#define SENSOR_SUB_TOPIC "iot/cmd/%s"
#endif

// Time intervals (in ticks)
#define INTERVAL_NORMAL    (5 * CLOCK_SECOND)  // Normal publish interval: 5s
#define INTERVAL_CON_MODE  (10 * CLOCK_SECOND) // Congestion mode interval: 10s

// ==========================================
// 2. GLOBAL VARIABLE DECLARATION
// ==========================================
static struct mqtt_connection conn;
static char client_id[32];
static char sub_topic[64];
static char app_buffer[256];
static struct etimer publish_timer;

// Device operational state variables
static clock_time_t current_publish_interval = INTERVAL_NORMAL;
static char current_mode[15] = "normal";

// State machine
static uint8_t state;
#define STATE_INIT         0
#define STATE_REGISTERED   1
#define STATE_CONNECTING   2
#define STATE_CONNECTED    3
#define STATE_PUBLISHING   4
#define STATE_DISCONNECTED 5

PROCESS(wind_sensor_process, "Wind Sensor MQTT Process");
AUTOSTART_PROCESSES(&wind_sensor_process);

// ==========================================
// 3. HELPER FUNCTIONS
// ==========================================
// Convert IPv6 address to string for JSON payload
static int ipaddr_sprintf(char *buf, uint8_t buf_len, const uip_ipaddr_t *addr) {
  uint16_t a;
  uint8_t len = 0;
  int i, f;
  for(i = 0, f = 0; i < sizeof(uip_ipaddr_t); i += 2) {
    a = (addr->u8[i] << 8) + addr->u8[i + 1];
    if(a == 0 && f >= 0) {
      if(f++ == 0) len += snprintf(&buf[len], buf_len - len, "::");
    } else {
      if(f > 0) f = -1;
      else if(i > 0) len += snprintf(&buf[len], buf_len - len, ":");
      len += snprintf(&buf[len], buf_len - len, "%x", a);
    }
  }
  return len;
}

// Check connectivity with the Border Router
static bool have_connectivity(void) {
  return (uip_ds6_get_global(ADDR_PREFERRED) != NULL && uip_ds6_defrt_choose() != NULL);
}

// ==========================================
// 4. MQTT EVENT HANDLING (RECEIVE COMMANDS FROM CLOUD)
// ==========================================
static void mqtt_event(struct mqtt_connection *m, mqtt_event_t event, void *data) {
  switch(event) {
    case MQTT_EVENT_CONNECTED:
      LOG_INFO("Connected to MQTT Broker!\n");
      state = STATE_CONNECTED;
      break;

    case MQTT_EVENT_PUBLISH: {
      // This is where cloud control commands are handled
      struct mqtt_message *msg_ptr = data;
      LOG_INFO("Received command from Cloud (Topic: %s): %.*s\n", 
               msg_ptr->topic, msg_ptr->payload_chunk_length, msg_ptr->payload_chunk);
      
      // Handle "con_mode" command (Congestion Mode)
      if(strncmp((const char *)msg_ptr->payload_chunk, "con_mode", msg_ptr->payload_chunk_length) == 0) {
        LOG_INFO("Switching to CON_MODE: reduce publish rate to 10s.\n");
        strncpy(current_mode, "con_mode", sizeof(current_mode));
        current_publish_interval = INTERVAL_CON_MODE;
      } 
      // Handle "normal" command (Restore normal mode)
      else if(strncmp((const char *)msg_ptr->payload_chunk, "normal", msg_ptr->payload_chunk_length) == 0) {
        LOG_INFO("Switching to NORMAL: publish rate 5s.\n");
        strncpy(current_mode, "normal", sizeof(current_mode));
        current_publish_interval = INTERVAL_NORMAL;
      }
      break;
    }

    case MQTT_EVENT_DISCONNECTED:
      LOG_INFO("Lost MQTT Broker connection.\n");
      state = STATE_DISCONNECTED;
      process_poll(&wind_sensor_process);
      break;

    case MQTT_EVENT_PUBACK:
      // Publish succeeded
      break;

    default:
      break;
  }
}

// ==========================================
// 5. PACKAGE AND SEND DATA
// ==========================================
static void publish_telemetry(void) {
  char ip_str[40];
  memset(ip_str, 0, sizeof(ip_str));
  
  if(uip_ds6_get_global(ADDR_PREFERRED) != NULL) {
    ipaddr_sprintf(ip_str, sizeof(ip_str), &uip_ds6_get_global(ADDR_PREFERRED)->ipaddr);
  }

  // Split float values to avoid %f issues on microcontrollers
  int v_int = 48 + (random_rand() % 3);
  int v_frac = random_rand() % 10;
  int i_int = 10 + (random_rand() % 2);
  int i_frac = random_rand() % 10;
  
  unsigned long sent_ms = clock_seconds() * 1000;

  // Create JSON string
  snprintf(app_buffer, sizeof(app_buffer),
    "{"
    "\"node_id\":\"%s\","
    "\"type\":\"wind\","
    "\"proto\":\"MQTT\","
    "\"ip\":\"%s\","
    "\"v\":%d.%d,"
    "\"i\":%d.%d,"
    "\"anomaly\":0,"
    "\"sent_ms\":%lu,"
    "\"mode\":\"%s\"" // Get current operational mode and attach to data
    "}",
    client_id, ip_str, v_int, v_frac, i_int, i_frac, sent_ms, current_mode);

  LOG_INFO("Publishing Telemetry: %s\n", app_buffer);
  
  // Publish to configured topic (default: iot/telemetry)
  mqtt_publish(&conn, NULL, SENSOR_PUB_TOPIC, (uint8_t *)app_buffer, strlen(app_buffer), MQTT_QOS_LEVEL_0, MQTT_RETAIN_OFF);
}

// ==========================================
// MAIN LOOP
// ==========================================
PROCESS_THREAD(wind_sensor_process, ev, data) {
  PROCESS_BEGIN();

  // 1. Create Client ID (e.g. prod_wind_a1b2)
  snprintf(client_id, sizeof(client_id), "prod_wind_%02x%02x", 
           linkaddr_node_addr.u8[6], linkaddr_node_addr.u8[7]);
           
  // 2. Create command subscription topic using configured pattern (default: iot/cmd/prod_wind_a1b2)
  snprintf(sub_topic, sizeof(sub_topic), SENSOR_SUB_TOPIC, client_id);
           
  LOG_INFO("Starting MQTT Client: %s\n", client_id);

  state = STATE_INIT;
  etimer_set(&publish_timer, CLOCK_SECOND);

  while(1) {
    PROCESS_YIELD(); // Sleep waiting for timer

    if(ev == PROCESS_EVENT_TIMER && data == &publish_timer) {
      switch(state) {
        case STATE_INIT:
          mqtt_register(&conn, &wind_sensor_process, client_id, mqtt_event, 256);
          conn.auto_reconnect = 0;
          state = STATE_REGISTERED;
          
        case STATE_REGISTERED:
          if(have_connectivity()) {
            LOG_INFO("Connected to IPv6, connecting to Broker...\n");
            mqtt_connect(&conn, MQTT_CLIENT_BROKER_IP_ADDR, MQTT_BROKER_PORT, 60, MQTT_CLEAN_SESSION_ON);
            state = STATE_CONNECTING;
          }
          etimer_set(&publish_timer, 2 * CLOCK_SECOND);
          break;
          
        case STATE_CONNECTING:
          etimer_set(&publish_timer, 1 * CLOCK_SECOND);
          break;
          
        case STATE_CONNECTED:
          // After successful connection, subscribe to command topic first
          LOG_INFO("Subscribing to: %s\n", sub_topic);
          mqtt_subscribe(&conn, NULL, sub_topic, MQTT_QOS_LEVEL_0);
          state = STATE_PUBLISHING;
          etimer_set(&publish_timer, 1 * CLOCK_SECOND); // Wait one tick before starting to send
          break;
          
        case STATE_PUBLISHING:
          if(mqtt_ready(&conn) && conn.out_buffer_sent) {
            publish_telemetry();
          }
          // Use dynamic interval (can change when command is received)
          etimer_set(&publish_timer, current_publish_interval); 
          break;
          
        case STATE_DISCONNECTED:
          LOG_INFO("Backing off and retrying connection...\n");
          mqtt_disconnect(&conn);
          state = STATE_REGISTERED;
          etimer_set(&publish_timer, 5 * CLOCK_SECOND);
          break;
      }
    }
  }

  PROCESS_END();
}