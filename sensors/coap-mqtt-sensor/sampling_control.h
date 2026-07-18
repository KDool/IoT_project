#ifndef SAMPLING_CONTROL_H_
#define SAMPLING_CONTROL_H_

#include <stdbool.h>
#include <stdint.h>

#include "contiki.h"

clock_time_t publish_interval_to_ticks(uint32_t interval_ms);
uint32_t get_publish_interval_ms(void);
void set_publish_interval_ms(uint32_t interval_ms);
bool publish_interval_is_dirty(void);
void publish_interval_clear_dirty(void);

#endif /* SAMPLING_CONTROL_H_ */
