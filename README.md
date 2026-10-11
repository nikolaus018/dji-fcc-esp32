# dji

ESP32-S3 firmware that switches a DJI N1 remote to FCC mode over USB, replacing the Android app
[DJI-FCC-HACK](https://github.com/M4TH1EU/DJI-FCC-HACK) (the two packets come from that project, credit to galbb on MavicPilots).

## Two ways to run it

* **Dev board** (any ESP32-S3 with a native USB port): default build, instructions below.
* **Custom PCB** (battery powered dongle, charge over USB-C, sleeps between uses): see [`hardware/`](hardware/README.md).
  Build the firmware for it with
  ```bash
  idf.py -B build_custom -DSDKCONFIG=sdkconfig.custom -DSDKCONFIG_DEFAULTS=sdkconfig.board_custom -DIDF_TARGET=esp32s3 build
  ```

## Use (dev board)
1. Flash through the **COM** port: `idf.py -p <port> flash`
2. Close the **USB-OTG** solder pad on the board bottom so it can power the remote's port.
3. Power on the drone and remote, wait until connected. The phone must **not** be connected to the remote while patching.
4. Plug the board's **USB** port into the remote's **bottom** port.
5. LED: blue = waiting, yellow = sending, green = sent, red = error.
6. Unplug the board and connect your phone to the **top** port.

The patch must be repeated **every time** you power on the drone and remote.

FCC power is only legal in the US; power cycle the drone and remote to return to CE.

## Notes
- The remote reports 512-byte bulk packets on a full-speed link. `components/espressif__usb` is a copy of
  Espressif's USB host component with the MPS check in `hcd_dwc.c` relaxed, and `main/dji.c` sizes the
  non-periodic TX FIFO for it. Both are required.
- The CDC serial function is interface 2; interfaces 0/1 are DJI-proprietary.
- The LED code drives GPIO48 and GPIO38 (DevKitC-1 v1.0 / v1.1).
- `main/board.h` is the board abstraction (`board_devkit.c` / `board_custom.c`); `main/dji.c` holds the patch logic.
- The dev-board build was tested on a real remote; the custom-PCB firmware and the hardware are untested (see `hardware/README.md`).

## License
MIT for this project's own code (see `LICENSE`). `components/espressif__usb` is Apache-2.0 (Espressif), see its own `LICENSE`.
