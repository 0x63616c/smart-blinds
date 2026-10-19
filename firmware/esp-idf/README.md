# ESP32-C6 bring-up image — motor disabled

This application links the portable control core against ESP-IDF and reports status over the C6 native USB console. The board port is deliberately unconfigured: there are **no assigned motor GPIOs, radio credentials, sensor drivers or movement commands**. A configured board port and valid calibration are both absent, so the actuator gate refuses output. The eventual PCB must also hold bridge enable off with hardware during boot/reset.

Target: ESP32-C6, provisional 4 MB flash module. Toolchain: official ESP-IDF v5.5.4. Build from the repository root using the official container:

```sh
docker run --rm -v "$PWD:/project" -w /project/firmware/esp-idf \
  espressif/idf:v5.5.4 idf.py set-target esp32c6 build
```

Or activate an installed ESP-IDF v5.5.4 and run `idf.py set-target esp32c6 build` in this directory. The default build output is ignored. The container is a build dependency, not a background service. [Official IDF Docker instructions](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/tools/idf-docker-image.html)

This initial image is a compiler/linker check and a future USB bring-up aid. It does not validate an actual PCB, pin assignment, radio, sleep current, motor, gauge or charger. No device has been flashed by this task. The watchdog and high-rate actuator task must be implemented before the port can drive hardware; the present five-second log loop never drives anything.
