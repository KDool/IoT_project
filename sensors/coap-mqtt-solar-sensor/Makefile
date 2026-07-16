CONTIKI_PROJECT = coap-mqtt-solar-sensor
all: $(CONTIKI_PROJECT)

CONTIKI = ../../../contiki-ng

# CoAP resources are shared from the wind sensor directory
MODULES_REL += ../coap-mqtt-sensor/resources

# Build the solar-specific wrapper so it sees solar project-conf.h first.
PROJECT_SOURCEFILES += sampling_control.c

# CoAP + MQTT modules
include $(CONTIKI)/Makefile.dir-variables
MODULES += $(CONTIKI_NG_APP_LAYER_DIR)/coap
MODULES += $(CONTIKI_NG_APP_LAYER_DIR)/mqtt

PLATFORMS_ONLY = cooja native nrf52840

include $(CONTIKI)/Makefile.include
