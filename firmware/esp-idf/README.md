# ESP32-C6 bring-up image — motor disabled

This application links the portable control core against ESP-IDF and reports status over the C6 native USB console. The board port is deliberately unconfigured: there are **no assigned motor GPIOs, radio credentials, sensor drivers or movement commands**. A configured board port and valid calibration are both absent, so the actuator gate refuses output. The eventual PCB must also hold bridge enable off with hardware during boot/reset.

Target: ESP32-C6, provisional 4 MB flash module. Toolchain: official ESP-IDF v5.5.4. Build from the repository root using the official container:

The initial configuration uses the ESP-IDF default **single factory application partition**, with no OTA partitions or update implementation. It is a bring-up configuration, not the final production partition table.

```sh
docker run --rm -v "$PWD:/project" -w /project/firmware/esp-idf \
  espressif/idf:v5.5.4 idf.py -B /project/work/c6-build set-target esp32c6 build
```

Or activate an installed ESP-IDF v5.5.4 and run `idf.py set-target esp32c6 build` in this directory. The default build output is ignored. The container is a build dependency, not a background service. [Official IDF Docker instructions](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/tools/idf-docker-image.html)

This initial image is a compiler/linker check and a future USB bring-up aid. It does not validate an actual PCB, pin assignment, radio, sleep current, motor, gauge or charger. No device has been flashed by this task. The watchdog and high-rate actuator task must be implemented before the port can drive hardware; the present five-second log loop never drives anything.

## Verified build

On 2026-10-19 the command above completed successfully on the official ARM64 container. The application binary was 154,496 bytes (`0x25b80`); the initial 1 MiB application partition had 85% free space. This does not establish room for a complete radio application and two OTA slots.

- Container manifest digest: `sha256:b9f2d6ea1c19e0c9f7959bdb74a9e3c775642f9d0f3b841937c5fa3363db892b`
- Initial binary SHA-256: `5e9ffe12020bd5829a7c0b552ea8946461422711c62237efcc52bd6687bcdf1d`
- Build products remain in ignored `work/c6-build`; source revisions and build timestamps can change the binary hash.
