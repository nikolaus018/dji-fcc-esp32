// Board abstraction: the same patch logic runs on a plain ESP32-S3 dev board (powered from a PC/power bank,
// remote-port VBUS provided by the board) and on the custom dji-fcc-esp32 PCB (battery powered, boost + switch
// for the remote's VBUS, deep sleep between uses).
#pragma once
#include <stdbool.h>
#include <stdint.h>

void board_init(void);
void board_led(uint8_t r, uint8_t g, uint8_t b);    // 0 = off, non-zero = on (brightness where supported)
int board_battery_mv(void);                          // battery voltage in mV, -1 if the board cannot measure it
bool board_wait_remote_attach(int timeout_ms);       // true once a USB-C sink (the remote) is seen on CC
void board_remote_power(bool on);                    // 5 V to the remote's port (current limited on the PCB)
bool board_remote_fault(void);                       // switch reports over-current / reverse voltage
void board_wait_remote_detach(void);                 // returns once the remote has been unplugged
void board_sleep(void) __attribute__((noreturn));    // deep sleep, wakes when a remote is plugged in

#define BOARD_HAS_POWER_MGMT CONFIG_DJI_BOARD_CUSTOM
#define BOARD_LOW_BATTERY_MV 3300
