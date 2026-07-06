/*
 * coap-mqtt-diesel-sensor.c
 *
 * Entry point for the diesel generator sensor node.
 * All logic lives in the shared coap-mqtt-sensor.c — this file simply
 * pulls it in so Cooja/Contiki can find the project binary by name.
 *
 * Key differences (configured via project-conf.h):
 *   NODE_TYPE            = "diesel"
 *   SENSOR_DEFAULT_ON    = 0   (starts OFF)
 *   SENSOR_STARTUP_DELAY_S = 40 (40 s warm-up after "on" command)
 *   Voltage: 220–230 V, Current: 5–15 A  →  power 1.1–3.5 kW
 */

#include "../coap-mqtt-sensor/coap-mqtt-sensor.c"
