#include "sdkconfig.h"
#if CONFIG_DJI_BOARD_DEVKIT
#include "board.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "led_strip.h"

// Onboard RGB LED: GPIO48 on DevKitC-1 v1.0, GPIO38 on v1.1. Drive both, only one has an LED.
static const int LED_GPIOS[] = {48, 38};
static led_strip_handle_t leds[2];

void board_init(void)
{
    for (int i = 0; i < 2; i++) {
        led_strip_config_t strip = {.strip_gpio_num = LED_GPIOS[i], .max_leds = 1};
        led_strip_rmt_config_t rmt = {.resolution_hz = 10 * 1000 * 1000};
        if (led_strip_new_rmt_device(&strip, &rmt, &leds[i]) != ESP_OK) {
            leds[i] = NULL;
        }
    }
}

void board_led(uint8_t r, uint8_t g, uint8_t b)
{
    for (int i = 0; i < 2; i++) {
        if (leds[i]) {
            led_strip_set_pixel(leds[i], 0, r, g, b);
            led_strip_refresh(leds[i]);
        }
    }
}

int board_battery_mv(void) { return -1; }
bool board_wait_remote_attach(int timeout_ms) { (void)timeout_ms; return true; }
void board_remote_power(bool on) { (void)on; }   // the dev board feeds VBUS through the USB-OTG jumper
bool board_remote_fault(void) { return false; }
void board_wait_remote_detach(void) {}
bool board_charger_present(void) { return false; }
int board_charge_state(void) { return 0; }

void board_sleep(void)
{
    for (;;) {
        vTaskDelay(portMAX_DELAY);
    }
}
#endif
