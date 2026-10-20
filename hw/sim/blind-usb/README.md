# USB input checks

`checks.py` binds selected part identities to the source and optional locally
generated BOM, compares all physical pins with a separate specification, and
checks five deliberate wiring faults. It calculates conditional current-limit,
divider, resistor-power and capacitor estimates. `capacitor-bias.json` contains
samples interpolated from Samsung's public typical curves with source URLs.

These checks do not run IC models, emulate PD negotiation, prove inrush/timing
compliance, or establish ESD/surge immunity. The result explicitly reports NVM
programming, surge qualification and hardware testing as incomplete.
