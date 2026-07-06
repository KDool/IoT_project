/*
 * coap-solar-sensor.c
 *
 * Entry point for the solar sensor node.
 * All logic lives in the shared coap-mqtt-sensor.c — this file simply
 * pulls it in so Cooja/Contiki can find the project binary by name.
 *
 * NODE_TYPE is defined as "solar" in project-conf.h, which changes:
 *   - node_id  →  "prod_solar_XXYY"
 *   - MQTT "type" field  →  "solar"
 */

#include "../coap-mqtt-sensor/coap-mqtt-sensor.c"
