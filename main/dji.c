// Sends the DJI "FCC patch" to an N1 remote over USB (replaces the DJI-FCC-HACK Android app).
//
// Dev board:  plug the USB-OTG port into the remote's bottom port; the patch is sent whenever a remote appears.
// Custom PCB: powered from the battery, sleeps until a remote is plugged in, powers the remote's port,
//             sends the patch, shows the result on the LED, then goes back to sleep until the next plug-in.
#include <stdint.h>
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "usb/usb_host.h"
#include "usb/cdc_acm_host.h"
#include "board.h"

#define DJI_VID 0x2CA3
#define DJI_PID 0x1020

// Same bytes as Constants.kt in the original Android app (DJI-FCC-HACK, credit: galbb / MavicPilots)
static const uint8_t PATCH_1[] = {85, 13, 4, 33, 42, 31, 0, 0, 0, 0, 1, 0x86, 32};
static const uint8_t PATCH_2[] = {85, 24, 4, 32, 2, 9, 0, 0, 64, 9, 39, 0, 2, 72, 0,
                                  0xFF, 0xFF, 2, 0, 0, 0, 0, 0x81, 31};

static const char *TAG = "dji";
static QueueHandle_t dev_queue;

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

// Returns ESP_OK when both packets were accepted by the remote.
static esp_err_t patch_remote(void)
{
    const cdc_acm_host_device_config_t cfg = {
        .connection_timeout_ms = 2000,
        .out_buffer_size = 64,
        .event_cb = event_cb,
    };
    // Interfaces 0/1 are DJI-proprietary; the CDC-ACM serial function is interface 2 (data on 3).
    cdc_acm_dev_hdl_t dev;
    esp_err_t err = cdc_acm_host_open(DJI_VID, DJI_PID, 2, &cfg, &dev);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Could not open remote: %s", esp_err_to_name(err));
        return err;
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
        return ESP_OK;
    }
    ESP_LOGE(TAG, "Send failed: %s / %s", esp_err_to_name(e1), esp_err_to_name(e2));
    return ESP_FAIL;
}

__attribute__((unused)) static void blink(uint8_t r, uint8_t g, uint8_t b, int times)
{
    for (int i = 0; i < times; i++) {
        board_led(r, g, b);
        vTaskDelay(pdMS_TO_TICKS(150));
        board_led(0, 0, 0);
        vTaskDelay(pdMS_TO_TICKS(150));
    }
}

static void usb_start(void)
{
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
}

#if BOARD_HAS_POWER_MGMT
#define CHARGE_AWAKE_S 2      // time a computer gets to start talking to us after a wake-up
#define CHARGE_SLEEP_S 30

// Set once a plug-in has been dealt with, cleared when the remote is unplugged. Survives deep sleep, so a
// remote that stays plugged in is patched once and does not keep the board awake.
static RTC_DATA_ATTR bool handled;

// Charger / computer on J2: the USB data lines are switched to J2, so stay out of USB host mode (that would
// take the PHY away from the built-in USB-Serial-JTAG that `idf.py flash` talks to) and show the charge status.
// On a computer stay awake, deep sleep would drop USB. On a plain charger sleep between status updates: the
// awake ESP draws more than the TP4056's end-of-charge current, so the charge would never terminate.
static void charge_mode(void)
{
    ESP_LOGI(TAG, "J2 powered: charge / flash mode");
    for (int s = 0; board_charger_present(); s++) {
        switch (board_charge_state()) {
        case 1: board_led(255, 0, 0); break;      // charging: red
        case 2: board_led(0, 255, 0); break;      // full: green
        default: board_led(0, 0, 255); break;     // powered, not charging (no battery / fault)
        }
        if (s >= CHARGE_AWAKE_S && !board_usb_host_connected()) {
            board_charge_sleep(CHARGE_SLEEP_S);
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
    board_led(0, 0, 0);
}

// Battery powered PCB: one patch per plug-in, then back to deep sleep.
static void run(void)
{
    if (board_charger_present()) {
        charge_mode();
    }
    if (!board_wait_remote_attach(1000)) {
        handled = false;              // unplugged, or a spurious wake
        board_sleep();
    }
    if (handled) {
        board_sleep();                // still plugged in after the last attempt
    }
    handled = true;

    int mv = board_battery_mv();
    ESP_LOGI(TAG, "battery %d mV", mv);
    // A brown-out reset means the last attempt collapsed the battery under the remote's load.
    if (mv < BOARD_LOW_BATTERY_MV || esp_reset_reason() == ESP_RST_BROWNOUT) {
        blink(255, 0, 0, 5);          // too low to power the remote's port: ask for a charge
        board_sleep();
    }

    board_led(0, 0, 255);             // blue: remote seen, powering it
    usb_start();
    bool ok = false;
    for (int attempt = 0; attempt < 3 && !ok; attempt++) {
        xQueueReset(dev_queue);
        board_remote_power(true);
        uint8_t go;
        if (xQueueReceive(dev_queue, &go, pdMS_TO_TICKS(10000)) == pdTRUE) {
            vTaskDelay(pdMS_TO_TICKS(500));
            board_led(255, 160, 0);   // yellow: sending
            ok = patch_remote() == ESP_OK;
        } else if (board_remote_fault()) {
            ESP_LOGE(TAG, "port switch reports a fault (over-current)");
        }
        if (!ok) {
            board_remote_power(false);        // power-cycle the remote's USB and try again
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }
    board_remote_power(false);
    board_led(ok ? 0 : 255, ok ? 255 : 0, 0);
    vTaskDelay(pdMS_TO_TICKS(ok ? 3000 : 4000));
    board_sleep();
}
#else
// Dev board: stay up and patch every remote that shows up.
static void run(void)
{
    board_led(0, 0, 20);              // blue: waiting
    usb_start();
    ESP_LOGI(TAG, "Waiting for DJI remote (2CA3:1020) on the USB-OTG port...");
    uint8_t go;
    while (1) {
        if (xQueueReceive(dev_queue, &go, portMAX_DELAY) == pdTRUE) {
            vTaskDelay(pdMS_TO_TICKS(500));
            board_led(20, 12, 0);     // yellow: patching
            if (patch_remote() == ESP_OK) {
                board_led(0, 30, 0);  // green: success
            } else {
                board_led(30, 0, 0);  // red: error
            }
        }
    }
}
#endif

void app_main(void)
{
    dev_queue = xQueueCreate(4, sizeof(uint8_t));
    board_init();
    run();
}
