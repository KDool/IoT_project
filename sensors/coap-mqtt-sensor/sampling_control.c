#include "contiki.h"

#include <stdint.h>

#include "sys/log.h"
#define LOG_MODULE "Sampling"
#define LOG_LEVEL  LOG_LEVEL_INFO

#ifndef MQTT_PUBLISH_INTERVAL_MS
#define MQTT_PUBLISH_INTERVAL_MS 5000UL
#endif
#ifndef MQTT_PUBLISH_INTERVAL_STRESSED_MS
#define MQTT_PUBLISH_INTERVAL_STRESSED_MS 15000UL
#endif

extern struct process mqtt_sensor_process;

static uint32_t current_publish_interval_ms = MQTT_PUBLISH_INTERVAL_MS;
static bool publish_interval_dirty = false;

clock_time_t
publish_interval_to_ticks(uint32_t interval_ms)
{
  uint64_t ticks = ((uint64_t)interval_ms * CLOCK_SECOND + 999UL) / 1000UL;

  if(interval_ms > 0 && ticks == 0) {
    ticks = 1;
  }
  if(ticks > (uint64_t)0xFFFFUL) {
    ticks = (uint64_t)0xFFFFUL;
  }

  return (clock_time_t)ticks;
}

uint32_t
get_publish_interval_ms(void)
{
  return current_publish_interval_ms;
}

void
set_publish_interval_ms(uint32_t interval_ms)
{
  if(interval_ms == 0) {
    interval_ms = MQTT_PUBLISH_INTERVAL_MS;
  }

  if(interval_ms > MQTT_PUBLISH_INTERVAL_STRESSED_MS) {
    interval_ms = MQTT_PUBLISH_INTERVAL_STRESSED_MS;
  }

  if(interval_ms != current_publish_interval_ms) {
    current_publish_interval_ms = interval_ms;
    publish_interval_dirty = true;
    process_poll(&mqtt_sensor_process);
    LOG_INFO("[MQTT] Publish interval updated to %lu ms\n",
             (unsigned long)current_publish_interval_ms);
  }
}

bool
publish_interval_is_dirty(void)
{
  return publish_interval_dirty;
}

void
publish_interval_clear_dirty(void)
{
  publish_interval_dirty = false;
}
