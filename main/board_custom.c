#include "sdkconfig.h"
#if CONFIG_DJI_BOARD_CUSTOM
#include "board.h"
#include "driver/gpio.h"
#include "driver/usb_serial_jtag.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

// GPIO map of hardware/design.py (net -> pin)
#define PIN_CC1        1    // J1_CC1, ADC1_CH0, 33k pull-up to 3V3, remote pulls down with 5.1k
#define PIN_CC2        2    // J1_CC2, ADC1_CH1
#define PIN_VBAT_SENSE 4    // ADC1_CH3, 1M/1M divider from VBAT
#define PIN_BOOST_EN   6    // MT3608 EN
#define PIN_LOAD_EN    7    // TPS2553 EN
#define PIN_LOAD_FAULT 8    // TPS2553 /FAULT, external 100k pull-up
#define PIN_VCHG_SENSE 21   // J2 VBUS via 100k/150k divider (RTC GPIO); also the USB switch select
#define PIN_CHRG       39   // TP4056 /CHRG  (open drain, low = charging)
#define PIN_STDBY      38   // TP4056 /STDBY (open drain, low = done)
#define PIN_LED_R      42   // LED cathodes: anodes sit on VBAT, GPIO low = on
#define PIN_LED_G      41
#define PIN_LED_B      40

#define ADC_CH_CC1  ADC_CHANNEL_0
#define ADC_CH_CC2  ADC_CHANNEL_1
#define ADC_CH_VBAT ADC_CHANNEL_3
// Rp 33k to 3V3: an open CC pin reads >3 V, the remote's Rd (5.1k) ~0.44 V, the Ra (<=1.2k) of an
// electronically marked cable <0.12 V. Only Rd counts as "remote attached".
#define CC_OPEN_MV 1600
#define CC_RA_MV   220

static const char *TAG = "board";
static adc_oneshot_unit_handle_t adc;
static adc_cali_handle_t cali;

static int adc_mv(adc_channel_t ch)
{
    int sum = 0, raw = 0;
    for (int i = 0; i < 8; i++) {
        adc_oneshot_read(adc, ch, &raw);
        sum += raw;
    }
    int mv = 0;
    adc_cali_raw_to_voltage(cali, sum / 8, &mv);
    return mv;
}

// Sorts the two CC pins into "sees Rd" and "open" GPIO masks (a pin on Ra is in neither).
static void cc_read(uint64_t *rd, uint64_t *open)
{
    static const struct { adc_channel_t ch; int pin; } CC[] = {{ADC_CH_CC1, PIN_CC1}, {ADC_CH_CC2, PIN_CC2}};
    *rd = *open = 0;
    for (int i = 0; i < 2; i++) {
        int mv = adc_mv(CC[i].ch);
        if (mv >= CC_OPEN_MV) {
            *open |= BIT64(CC[i].pin);
        } else if (mv > CC_RA_MV) {
            *rd |= BIT64(CC[i].pin);
        }
    }
}

static bool cc_attached(void)
{
    uint64_t rd, open;
    cc_read(&rd, &open);
    return rd != 0;
}

void board_init(void)
{
    const gpio_config_t outs = {
        .pin_bit_mask = BIT64(PIN_BOOST_EN) | BIT64(PIN_LOAD_EN) | BIT64(PIN_LED_R) | BIT64(PIN_LED_G) | BIT64(PIN_LED_B),
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&outs);
    gpio_set_level(PIN_BOOST_EN, 0);
    gpio_set_level(PIN_LOAD_EN, 0);
    board_led(0, 0, 0);
    // board_charge_sleep() keeps the LED pins latched through deep sleep; release them again
    gpio_deep_sleep_hold_dis();
    gpio_hold_dis(PIN_LED_R);
    gpio_hold_dis(PIN_LED_G);
    gpio_hold_dis(PIN_LED_B);
    gpio_config(&(gpio_config_t){.pin_bit_mask = BIT64(PIN_LOAD_FAULT) | BIT64(PIN_VCHG_SENSE), .mode = GPIO_MODE_INPUT});
    gpio_config(&(gpio_config_t){.pin_bit_mask = BIT64(PIN_CHRG) | BIT64(PIN_STDBY), .mode = GPIO_MODE_INPUT,
                                 .pull_up_en = GPIO_PULLUP_ENABLE});

    adc_oneshot_unit_init_cfg_t unit = {.unit_id = ADC_UNIT_1};
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&unit, &adc));
    adc_oneshot_chan_cfg_t ch = {.atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT};
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, ADC_CH_CC1, &ch));
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, ADC_CH_CC2, &ch));
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, ADC_CH_VBAT, &ch));
    adc_cali_curve_fitting_config_t cc = {.unit_id = ADC_UNIT_1, .atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT};
    ESP_ERROR_CHECK(adc_cali_create_scheme_curve_fitting(&cc, &cali));
}

void board_led(uint8_t r, uint8_t g, uint8_t b)
{
    gpio_set_level(PIN_LED_R, !r);
    gpio_set_level(PIN_LED_G, !g);
    gpio_set_level(PIN_LED_B, !b);
}

int board_battery_mv(void)
{
    return adc_mv(ADC_CH_VBAT) * 2;   // 1M/1M divider
}

bool board_wait_remote_attach(int timeout_ms)
{
    int stable = 0;
    for (int t = 0; t <= timeout_ms; t += 50) {
        stable = cc_attached() ? stable + 1 : 0;
        if (stable >= 3) {
            return true;
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
    return false;
}

void board_remote_power(bool on)
{
    if (on) {
        gpio_set_level(PIN_BOOST_EN, 1);
        vTaskDelay(pdMS_TO_TICKS(20));      // let the 5 V rail come up before closing the switch
        gpio_set_level(PIN_LOAD_EN, 1);
    } else {
        gpio_set_level(PIN_LOAD_EN, 0);
        gpio_set_level(PIN_BOOST_EN, 0);
    }
}

bool board_remote_fault(void)
{
    return gpio_get_level(PIN_LOAD_FAULT) == 0;
}

bool board_charger_present(void)
{
    return gpio_get_level(PIN_VCHG_SENSE) == 1;
}

int board_charge_state(void)
{
    if (gpio_get_level(PIN_CHRG) == 0) {
        return 1;
    }
    return gpio_get_level(PIN_STDBY) == 0 ? 2 : 0;
}

bool board_usb_host_connected(void)
{
    return usb_serial_jtag_is_connected();
}

void board_sleep(void)
{
    board_remote_power(false);
    board_led(0, 0, 0);
    // Both CC pins idle high (33k pull-up); the remote's 5.1k Rd pulls one of them low. EXT1 is level
    // triggered, so arm it for the next change: unplug while a remote is attached, plug-in otherwise.
    uint64_t rd, open;
    cc_read(&rd, &open);
    if (rd) {
        ESP_LOGI(TAG, "deep sleep, waking when the remote is unplugged");
        esp_sleep_enable_ext1_wakeup_io(rd, ESP_EXT1_WAKEUP_ANY_HIGH);
    } else if (open) {
        ESP_LOGI(TAG, "deep sleep, waking when a remote is plugged in");
        esp_sleep_enable_ext1_wakeup_io(open, ESP_EXT1_WAKEUP_ANY_LOW);
    }
    // Plugging J2 into a charger/computer also wakes us (VBUS high) so USB flashing works from sleep.
    esp_sleep_enable_ext0_wakeup(PIN_VCHG_SENSE, 1);
    esp_deep_sleep_start();
}

void board_charge_sleep(int seconds)
{
    board_remote_power(false);
    gpio_hold_en(PIN_LED_R);
    gpio_hold_en(PIN_LED_G);
    gpio_hold_en(PIN_LED_B);
    gpio_deep_sleep_hold_en();
    esp_sleep_enable_timer_wakeup(seconds * 1000000ULL);
    esp_sleep_enable_ext0_wakeup(PIN_VCHG_SENSE, 0);   // J2 unplugged
    esp_deep_sleep_start();
}
#endif
