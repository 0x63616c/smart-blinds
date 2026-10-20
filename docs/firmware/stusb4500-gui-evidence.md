# STUSB4500 above-5 V NVM field evidence

The offline generator now sets `POWER_ONLY_ABOVE_5V` at **E6 bit 3**. This mapping comes from static inspection of the manufacturer's GUI resource, checkbox binding, forward serializer and inverse decoder. It is an inference from manufacturer executable code, not an explicit field table in the older NVM note, a GUI differential export or a hardware test. The generator remains `INCOMPLETE_DO_NOT_PROGRAM` because the discharge profile, baseline/silicon review and electrical acceptance tests remain outstanding.

## Exact primary artifact

ST's [pinned GUI package](https://github.com/usb-c/STUSB4500/blob/55d1109e7ef0cffc2ffef2494095d23306594601/GUI/App/STSW-STUSB002%20v1.0.8.zip) contains `STUSB4500_GUI_1.08.exe`, SHA-256 `a15e40a163123c5f15585fd8de2a8696b14b01a786583926ac3380f296fe5fce`. It is a native x86 PE binary with image base `0x400000`. The executable was read and disassembled, never launched, loaded as a library or connected to hardware. No executable is redistributed in this repository.

The later [ST GUI quick-start guide](https://www.st.com/resource/en/product_presentation/stswstusb002_quick_start_v3_2.pdf) also shows the same named option in version 2.00, but the audited code below is specifically version 1.08. This evidence is not a claim about every GUI or silicon revision. The older 39-page NVM note marks E6's low nibble reserved and therefore cannot alone establish this field.

## Forward and inverse chain

| Evidence | Location in the exact binary | Meaning |
|---|---|---|
| Dialog resource | File offset `0x1FBDC`; control ID immediately before its class/title | UTF-16 `POWER_ONLY_ABOVE_5V` checkbox has ID `0x45C` |
| Control binding | VA `0x40B116..0x40B123` | ID `0x45C` binds to dialog control member `+0x1098`; its HWND is at `+0x10B8` |
| Checkbox read | VA `0x40B515..0x40B52F` | `BM_GETCHECK` result is normalized to a boolean and stored at configuration member `+0x54` |
| Checkbox display | VA `0x40AE57..0x40AE70` | Configuration member `+0x54` controls `BM_SETCHECK` on the same HWND |
| NVM serializer | VA `0x40F005..0x40F034` | The boolean at configuration `+0x54` becomes bit 3 of image offset `0x26` |
| NVM decoder | VA `0x40F429..0x40F432` | Image byte `+0x26` shifted right 3 and masked with 1 is stored at configuration `+0x54` |

The image is the five eight-byte sectors beginning at C0, so image offset `0x26` is E6. The neighboring `REQ_SRC_CURRENT` checkbox (ID `0x45B`, configuration member `+0x53`) maps to E6 bit 4, independently agreeing with the documented NVM note. The forward serializer's reviewed algebra for this byte is:

```text
image[0x26] = (original & 0xA0)
            | ((config[0x52] & 1) << 6)
            | ((config[0x53] & 1) << 4)
            | ((config[0x54] & 1) << 3)
            |  (config[0x55] & 7)
```

Its inverse extracts those fields at shifts 6, 4, 3 and 0 respectively. The audit exhaustively checks all 16,384 combinations of original byte and represented fields, all 256 full-byte round trips, and all 512 single-checkbox toggles. Setting this checkbox alone changes only bit 3 and its inverse reads it as 1. These are algebraic checks of the reviewed instructions, not execution/emulation of the Windows binary.

## Reproduce without running the GUI

Extract the named executable from the pinned manufacturer archive into an ignored work directory. Run:

```sh
python3 firmware/tools/stusb4500_gui_audit.py work/stusb4500-primary/STUSB4500_GUI_1.08.exe
```

The tool requires the exact SHA-256, parses PE sections to locate the recorded instruction bytes, checks the checkbox resource ID/title and emits the forward/inverse results. A different binary is rejected. For independent inspection, use an x86-capable disassembler on the listed addresses; the script preserves the short instruction signatures so an audit does not depend on prose alone. The standard factory tests also verify that every possible original E6 byte becomes `(original & ~0x18) | 0x08`, preserving all unrelated bits while enabling above-5 V gating and clearing `REQ_SRC_CURRENT`.

This removes the missing field-location gate from the offline proposal. It does **not** authorize programming or prove autonomous VBUS gating. Factory acceptance still requires full readback, reset/reload, 5 V blocking, accepted 9/15 V contracts, insufficient-current rejection, detach/hard-reset behavior and measured discharge timing on the actual circuit. See the [factory procedure](stusb4500-factory.md).
