# Protected carrier candidate parts

These are fresh atomic wrappers generated from public EasyEDA supplier geometry.
The exact manufacturer/supplier identities are in each wrapper and in the dated
`bom/electronics-carrier-sourcing.json`. Public overseas stock is not reserved
in-house assembly stock. No purchasing or fabrication has occurred.

- AON7400A C85734: manufacturer Full Production; 30 V, ±20 V gate,10.5 mΩ maximum
  at4.5 V/25°C. 1–3 are source,4 gate,5–8 and the exposed pad9 are drain. The
  [primary package drawing PO-00047I](https://www.aosmd.com/sites/default/files/res/packaging_information/DFN3x3A_8L_EP1_P.pdf)
  defines the corrected pads. Three repeated pad9 copper regions implement its
  continuous drain; four paste windows require assembler review. AON7418 was
  rejected as NRND and its suggested AON7318 replacement as obsolete.
- Littelfuse0451003.MRL C13982: 3 A branch-fuse candidate. Primary recommended pads
  are1.96×3.15 mm, with2.95 mm gap; body6.10±0.20×2.69±0.25 mm and height2.69±0.25.
  [Manufacturer series data](https://www.littelfuse.cn/assetdocs/fuse-451-and-453-datasheet?assetguid=533cd5cc-956c-4243-867f-6ab5a62f6ba1)
  is authoritative over inconsistent catalogue I²t/resistance values.
- VishayWSL2512R0100FEA C844901: 10 mΩ±1%,75 ppm/°C,1 W at70°C. Corrected pads
  are1.65×3.68 mm with4.06 mm gap for this resistance range, from the
  [manufacturer WSL document30100](https://www.vishay.com/docs/30100/wsl.pdf).
- SamsungCL21B474KBFNNNE C13967: active Mass Production,470 nF50 V X7R±10%,0805;
  [primary product page](https://product.samsungsem.com/mlcc/CL21B474KBFNNN.do).
  JLC Basic at the observed snapshot. Nominal bypass is not proof of biased
  capacitance or regulator/charge-pump stability.
- JSCJBZT52C4V7 C2116: pin1 cathode,2 anode. Primary manufacturer family PDF,
  hosted by its supplier: [BZT52C series](https://datasheet.lcsc.com/datasheet/pdf/748504625e418aa84c5305d597e87d6d.pdf).
  4.4–5.0 V is specified at5 mA; leakage is specified at2 V, not3.3 V. Bus leakage,
  capacitance and ESD overshoot remain measured qualification items.

`make_wrappers.py` reproduces pin aliases and the explicit footprint corrections;
run it with the atopile Python containing sexpdata. Do not treat generic imports,
3D models, catalogue current ratings or an unrouted build as physical acceptance.
