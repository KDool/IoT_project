CONTIKI_PROJECT = coap-mqtt-battery-sensor
all: $(CONTIKI_PROJECT)

CONTIKI = ../../../contiki-ng

MODULES_REL += ./resources

# CoAP modules
include $(CONTIKI)/Makefile.dir-variables
MODULES += $(CONTIKI_NG_APP_LAYER_DIR)/coap

PLATFORMS_ONLY = cooja native nrf52840

include $(CONTIKI)/Makefile.include
