# Default-unqualified Wi-Fi motion target

Separate from the unchanged [radio-only evaluation](../esp-idf-wifi/README.md).
This image connects authenticated Wi-Fi resources to the existing owned motion
runtime, power readers and C6 port. **It ships with empty physical records,
the bench motion option OFF, and no physical reference. It cannot move a motor.**

Without previously approved encrypted Wi-Fi configuration it does not join or
initialize board GPIO. With radio/OFF-pin approval alone it uses permanently held
OFF outputs. The qualified control-owner branch is mutually exclusive with that
branch: it never releases or inherits those holds. Enabling a compile flag does
not manufacture measurements, pack qualification or a reference.

The [runtime contract](../../docs/firmware/wifi-motion.md) describes cancellation,
raw button STOP/wake, physical parking evidence and remaining qualification.
No credentials or physical qualification are provided. There is no provisioning,
charge-enable, OTA or local tap-to-endpoint service.

## Reproducible builds

From the repository root:

```sh
sh firmware/esp-idf-wifi/fetch_dependencies.sh
docker run --rm -v "$PWD:/project" -w /project/firmware/esp-idf-wifi-motion \
  espressif/idf:v5.5.4@sha256:b9f2d6ea1c19e0c9f7959bdb74a9e3c775642f9d0f3b841937c5fa3363db892b \
  idf.py -D SB_COAP_DIR=/project/work/wifi-idf-extra/coap \
    -B /project/work/c6-wifi-motion-build set-target esp32c6 build
```

The vendor pins and per-directory Git verification are identical to the
evaluation: `idf-extra-components` **cad43839020fc329722035a35640a54e06fee09b**,
libcoap **d9b4031ee61df1a40ecec46fe3817a1f985b3919**, GCC 14.2.0
`esp-14.2.0_20260121`. No download occurs implicitly during configuration.

The explicit compile-coverage variant exercises the C6 initialization branch,
while the application still supplies empty records and cannot initialize it:

```sh
docker run --rm -v "$PWD:/project" -w /project/firmware/esp-idf-wifi-motion \
  espressif/idf:v5.5.4@sha256:b9f2d6ea1c19e0c9f7959bdb74a9e3c775642f9d0f3b841937c5fa3363db892b \
  idf.py -D SB_COAP_DIR=/project/work/wifi-idf-extra/coap \
    -D SDKCONFIG=/project/work/c6-wifi-motion-bench.sdkconfig \
    -D 'SDKCONFIG_DEFAULTS=/project/firmware/esp-idf-wifi-motion/sdkconfig.defaults;/project/firmware/esp-idf-wifi-motion/bench-compile.defaults' \
    -B /project/work/c6-wifi-motion-bench set-target esp32c6 build
```

Local build evidence is recorded in the runtime contract; fresh pinned CI must
establish the result for the published source. Both OTA-sized slots remain
reserved; no update implementation exists. No hardware was flashed.
