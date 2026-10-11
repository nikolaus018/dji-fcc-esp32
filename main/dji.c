// Sends the DJI "FCC patch" to an N1 remote over USB (replaces the DJI-FCC-HACK Android app).
// Plug the ESP32-S3 USB-OTG port into the remote's bottom USB port; the patch is sent on connect.
#include <stdint.h>
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "usb/usb_host.h"
#include "usb/cdc_acm_host.h"
#include "led_strip.h"

#define DJI_VID 0x2CA3
#define DJI_PID 0x1020

// Same bytes as Constants.kt in dji-fcc
static const uint8_t PATCH_1[] = {85, 13, 4, 33, 42, 31, 0, 0, 0, 0, 1, 0x86, 32};
static const uint8_t PATCH_2[] = {85, 24, 4, 32, 2, 9, 0, 0, 64, 9, 39, 0, 2, 72, 0,
                                  0xFF, 0xFF, 2, 0, 0, 0, 0, 0x81, 31};

static const char *TAG = "dji";
static QueueHandle_t dev_queue;

// Onboard RGB LED: GPIO48 on DevKitC-1 v1.0, GPIO38 on v1.1. Drive both, only one has an LED.
static const int LED_GPIOS[] = {48, 38};
static led_strip_handle_t leds[2];

static void led_set(uint8_t r, uint8_t g, uint8_t b)
{
    for (int i = 0; i < 2; i++) {
        if (leds[i]) {
            led_strip_set_pixel(leds[i], 0, r, g, b);
            led_strip_refresh(leds[i]);
        }
    }
}

static void led_init(void)
{
    for (int i = 0; i < 2; i++) {
        led_strip_config_t strip = {.strip_gpio_num = LED_GPIOS[i], .max_leds = 1};
        led_strip_rmt_config_t rmt = {.resolution_hz = 10 * 1000 * 1000};
        if (led_strip_new_rmt_device(&strip, &rmt, &leds[i]) != ESP_OK) {
            leds[i] = NULL;
        }
    }
}

static void usb_lib_task(void *arg)
{
    while (1) {
        uint32_t flags;
        usb_host_lib_handle_events(portMAX_DELAY, &flags);
    }
}

static void new_dev_cb(usb_device_handle_t usb_dev)
{
    const usb_device_desc_t *desc;
    if (usb_host_get_device_descriptor(usb_dev, &desc) != ESP_OK) {
        return;
    }
    ESP_LOGI(TAG, "USB device %04X:%04X", desc->idVendor, desc->idProduct);
    if (desc->idVendor == DJI_VID && desc->idProduct == DJI_PID) {
        uint8_t go = 1;
        xQueueSend(dev_queue, &go, 0);
    }
}

static void event_cb(const cdc_acm_host_dev_event_data_t *event, void *user_ctx)
{
    if (event->type == CDC_ACM_HOST_DEVICE_DISCONNECTED) {
        ESP_LOGI(TAG, "Remote disconnected");
        cdc_acm_host_close(event->data.cdc_hdl);
    }
}

static void patch_remote(void)
{
    const cdc_acm_host_device_config_t cfg = {
        .connection_timeout_ms = 2000,
        .out_buffer_size = 64,
        .event_cb = event_cb,
    };
    led_set(20, 12, 0); // yellow: patching
    // Interfaces 0/1 are DJI-proprietary; the CDC-ACM serial function is interface 2 (data on 3).
    cdc_acm_dev_hdl_t dev;
    if (cdc_acm_host_open(DJI_VID, DJI_PID, 2, &cfg, &dev) != ESP_OK) {
        ESP_LOGE(TAG, "Could not open remote");
        led_set(30, 0, 0); // red: error
        return;
    }

    const cdc_acm_line_coding_t lc = {.dwDTERate = 19200, .bCharFormat = 0, .bParityType = 0, .bDataBits = 8};
    cdc_acm_host_line_coding_set(dev, &lc);
    cdc_acm_host_set_control_line_state(dev, true, true);
    vTaskDelay(pdMS_TO_TICKS(100));

    esp_err_t e1 = cdc_acm_host_data_tx_blocking(dev, PATCH_1, sizeof(PATCH_1), 1000);
    esp_err_t e2 = cdc_acm_host_data_tx_blocking(dev, PATCH_2, sizeof(PATCH_2), 1000);
    cdc_acm_host_close(dev);

    if (e1 == ESP_OK && e2 == ESP_OK) {
        ESP_LOGI(TAG, "FCC patch sent. Move your phone to the TOP port.");
        led_set(0, 30, 0); // green: success
    } else {
        ESP_LOGE(TAG, "Send failed: %s / %s", esp_err_to_name(e1), esp_err_to_name(e2));
        led_set(30, 0, 0); // red: error
    }
}

void app_main(void)
{
    dev_queue = xQueueCreate(4, sizeof(uint8_t));
    led_init();
    led_set(0, 0, 20); // blue: waiting for remote

    // The remote declares 512-byte bulk packets; give the non-periodic TX FIFO room for a full one.
    const usb_host_config_t host_cfg = {
        .intr_flags = ESP_INTR_FLAG_LEVEL1,
        .fifo_settings_custom = {.nptx_fifo_lines = 128, .ptx_fifo_lines = 4, .rx_fifo_lines = 68},
    };
    ESP_ERROR_CHECK(usb_host_install(&host_cfg));
    xTaskCreate(usb_lib_task, "usb_lib", 4096, NULL, 20, NULL);

    const cdc_acm_host_driver_config_t drv_cfg = {
        .driver_task_stack_size = 4096,
        .driver_task_priority = 21,
        .xCoreID = 0,
        .new_dev_cb = new_dev_cb,
    };
    ESP_ERROR_CHECK(cdc_acm_host_install(&drv_cfg));

    ESP_LOGI(TAG, "Waiting for DJI remote (2CA3:1020) on the USB-OTG port...");
    uint8_t go;
    while (1) {
        if (xQueueReceive(dev_queue, &go, portMAX_DELAY) == pdTRUE) {
            vTaskDelay(pdMS_TO_TICKS(500));
            patch_remote();
        }
    }
}
