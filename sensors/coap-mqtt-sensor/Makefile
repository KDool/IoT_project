CONTIKI_PROJECT = coap-mqtt-sensor
all: $(CONTIKI_PROJECT)

CONTIKI = ../../../contiki-ng

# Include CoAP resources in ./resources/
MODULES_REL += ./resources

# CoAP + MQTT modules
include $(CONTIKI)/Makefile.dir-variables
MODULES += $(CONTIKI_NG_APP_LAYER_DIR)/coap
MODULES += $(CONTIKI_NG_APP_LAYER_DIR)/mqtt

PLATFORMS_ONLY = cooja native nrf52840

include $(CONTIKI)/Makefile.include
