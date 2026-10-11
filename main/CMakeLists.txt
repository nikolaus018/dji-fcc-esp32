idf_component_register(SRCS "dji.c" "board_devkit.c" "board_custom.c"
                    INCLUDE_DIRS "."
                    PRIV_REQUIRES esp_driver_gpio esp_driver_usb_serial_jtag esp_adc)
