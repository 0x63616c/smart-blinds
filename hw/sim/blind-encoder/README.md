# Encoder supply checks

`checks.py` verifies exact part identities and an independent physical-pin
contract, rejects four wiring mutations, and calculates conditional capacitor,
load and heat estimates. `capacitor-bias.json` retains the manufacturer curve
bracketing points used for interpolation. The results are not a dynamic LDO,
encoder or thermal simulation. See the board README for the qualification gaps.
