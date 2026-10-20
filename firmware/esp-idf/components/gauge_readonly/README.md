# MAX17320 read-only C6 transport

This ESP-IDF component compiles against the real I2C master API. It attaches two device addresses to an already configured, externally pulled-up bus. It has no pin defaults, no bus creation, and no data-register write or NVM command path. The bring-up application depends on it for compilation but does not attach or call it.

Each pointer/read transaction requests a 10 ms timeout; the 15-register capture has a 250 ms software budget and reports failure on the first bus error. IDF/RTOS scheduling and actual stuck-bus behavior need bench verification: these are requested software deadlines, not a proved physical cutoff. Only a dedicated sensor worker may call it. The motor task and independent hardware protection must not wait for this reader. [ESP-IDF I2C API](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32c6/api-reference/peripherals/i2c.html)

`GaugeReadback.valid` means all requested bus reads succeeded within the capture budget. It does **not** mean the pack profile, cell health, sensor freshness, temperature or protection setup is acceptable. It must never be assigned directly to `Measurement.power_ready`. The future pack supervisor must validate identity/profile, individual cells, protection flags, ADC-age bounds and charger state. Gauge values can update more slowly than the host reads them. [Commissioning requirements](../../../../docs/firmware/max17320-commissioning.md)

Calls and destruction belong to one worker. The worker owns reader lifetime; the application owns the bus and must detach devices before deleting it. Recovery from a timeout must keep charging/motion inhibited, use a bounded bus recovery policy, and reacquire a full healthy snapshot. It must never restart an interrupted move.

Validation scope: target compile/link, alongside existing offline register arithmetic/readback tests. No I2C fixture, hot plug or real pack test has been performed.
