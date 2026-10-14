CONTIKI_PROJECT = ranger-rs-wire-rpl

PROJECT_SOURCEFILES += ranger_rs_codec.c

RANGER_RS_WIRE_MODE ?= 0

DEFINES += RANGER_RS_WIRE_MODE=$(RANGER_RS_WIRE_MODE)

all: $(CONTIKI_PROJECT)

CONTIKI = ../../../../third_party/contiki-ng

include $(CONTIKI)/Makefile.include
