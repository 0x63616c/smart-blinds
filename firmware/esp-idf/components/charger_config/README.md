# Charge-disabled BQ25798 component

Bounded ESP-IDF I2C adapter for the [portable configuration/capture policy](../../../include/smart_blinds/charger.hpp).
See the [register image, evidence requirements and validation scope](../../../../docs/firmware/charger-configuration.md).

The caller owns a reviewed I2C bus and an independent `Inhibit` implementation.
This component configures no pins and exposes no charge-enable operation. It
keeps `EN_CHG=0`; the bring-up app does not instantiate it. Attach/detach discard
configuration. Never call it from a motor-control or radio callback task.

The bus uses address 0x6B at 100 kHz, a 10 ms transfer timeout, a 750 ms operation
budget and a finite ADC polling cap. Actual electrical timing and bus isolation
still require validation. Native C6 compilation is a separate gate from the
passing fake-bus host tests.
