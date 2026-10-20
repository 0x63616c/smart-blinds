# Solder landing features

These are PCB copper and holes, not purchased parts. `has_part_removed` keeps
them out of the assembly BOM while preserving electrical connectivity and
footprints. They require no feeder, but the wires still require assembly labor.

`WirePad18` uses a 4 mm copper land and 1.5 mm finished hole; `WirePadSignal`
uses a 2.5 mm land and 1.2 mm hole. These are design choices, not a solder-process
qualification. All six conductors in the selected protected pack cable are
18 AWG, including telemetry, so all six use the larger landing.

Use one wire per hole and separate mechanical strain relief. Check actual
stripped/tinned strand fit before release. Keep exposed ends and solder fillets
within the cassette's opposed-board clearance; no uninsulated tail may approach
the other carrier. Do not use solder joints as the wire-retention mechanism.
