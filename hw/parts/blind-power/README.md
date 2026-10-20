# Charger support parts

These public EasyEDA/LCSC imports support the fresh charger capture. Atomic
wrappers pin exact manufacturer/LCSC identities; they do not encode full electrical
ratings. The charger manifest records those separately. Source symbol pin types
are mostly passive/unspecified, so meaningful native ERC needs reviewed types.

MMBT3906LT1G B1/E2/C3 and AO3400A G1/S2/D3 were checked against manufacturer
pin drawings. Passive values/ratings are documented in the charger manifest.
The inductor's manufacturer body is 7.0 ±0.3 ×6.6 ±0.3 ×3.0 mm maximum; the imported
footprint name contains 7.2 mm and is not proof of its recommended land pattern.
The REGN capacitor is active-production CL21A475KAQNNNE, 4.7 µF/25 V/0805
(C1779). The unused CL10A475KO8NNNC import is NRND and must not be selected.

`make_wrappers.py` splits the combined library and makes adjacent footprint copies
for atopile 0.15.9. It needs Python with `sexpdata`. The manually copied 10 µF Samsung
wrapper is retained separately. Relative 3D paths target layouts nested three
levels below `hw`; 3D models are visual aids, not dimensional acceptance evidence.

No footprint, solderability, assembly yield or physical circuit has been tested.
