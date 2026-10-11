#include "sdkconfig.h"
#if CONFIG_DJI_BOARD_CUSTOM
#include "board.h"
#include "driver/gpio.h"
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
#define PIN_LED_R      42   // LED cathodes: anodes sit on VBAT, GPIO low = on
#define PIN_LED_G      41
#define PIN_LED_B      40

#define ADC_CH_CC1  ADC_CHANNEL_0
#define ADC_CH_CC2  ADC_CHANNEL_1
#define ADC_CH_VBAT ADC_CHANNEL_3
#define CC_ATTACHED_MV 1600   // Rp 33k to 3V3 against Rd 5.1k reads ~0.44 V; open CC reads >3 V

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

static bool cc_attached(void)
{
    return adc_mv(ADC_CH_CC1) < CC_ATTACHED_MV || adc_mv(ADC_CH_CC2) < CC_ATTACHED_MV;
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
    gpio_config(&(gpio_config_t){.pin_bit_mask = BIT64(PIN_LOAD_FAULT), .mode = GPIO_MODE_INPUT});

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

void board_wait_remote_detach(void)
{
    int gone = 0;
    while (gone < 5) {
        gone = cc_attached() ? 0 : gone + 1;
        vTaskDelay(pdMS_TO_TICKS(200));
    }
}

void board_sleep(void)
{
    board_remote_power(false);
    board_led(0, 0, 0);
    ESP_LOGI(TAG, "deep sleep, waking when a remote is plugged in");
    // Both CC pins idle high (33k pull-up); the remote's 5.1k Rd pulls one of them low.
    esp_sleep_enable_ext1_wakeup_io(BIT64(PIN_CC1) | BIT64(PIN_CC2), ESP_EXT1_WAKEUP_ANY_LOW);
    esp_deep_sleep_start();
}
#endif
