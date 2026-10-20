#!/usr/bin/env python3
"""Verify the exact ST GUI artifact used for a static NVM-field audit.

Reads bytes only. Never loads, executes or emulates the Windows executable.
The reviewed instruction semantics are explained in stusb4500-gui-evidence.md.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct

GUI_SHA256 = "a15e40a163123c5f15585fd8de2a8696b14b01a786583926ac3380f296fe5fce"
GUI_SOURCE = "https://github.com/usb-c/STUSB4500/blob/55d1109e7ef0cffc2ffef2494095d23306594601/GUI/App/STSW-STUSB002%20v1.0.8.zip"
BLOCKS = {
    "checkbox_bind": (0x40B116, "8d879810000050685c04000056e8da610000"),
    "checkbox_get": (0x40B515, "ffb6b8100000ff15705141006a0085c06a000f95c068f0000000884754"),
    "checkbox_set": (0x40AE57, "807e54006a0074046a01eb026a0068f1000000ffb7b8100000ffd3"),
    "serializer": (0x40F005, "0fb64e520fb6465380e1012401c0e1020ac80fb64654240102c90ac80fb646552407c0e1030ac80fb6422624a00ac8884a26"),
    "decoder": (0x40F411, "0fb64626c0e80624018842520fb64626c0e80424018842530fb64626c0e80324018842540fb646262407884255"),
}


def reviewed_encode(original: int, s52: int, s53: int, s54: int, s55: int) -> int:
    """Algebraic transcription of the reviewed serializer, not binary execution."""
    return ((original & 0xA0) | ((s52 & 1) << 6) | ((s53 & 1) << 4)
            | ((s54 & 1) << 3) | (s55 & 7))


def reviewed_decode(value: int) -> tuple[int, int, int, int]:
    return ((value >> 6) & 1, (value >> 4) & 1, (value >> 3) & 1, value & 7)


def check_bijection() -> dict:
    cases = 0
    for original in range(256):
        if reviewed_encode(original, *reviewed_decode(original)) != original:
            raise ValueError("reviewed round trip differs")
        for fields in range(64):
            s52, s53, s54, s55 = (fields >> 5) & 1, (fields >> 4) & 1, (fields >> 3) & 1, fields & 7
            encoded = reviewed_encode(original, s52, s53, s54, s55)
            if reviewed_decode(encoded) != (s52, s53, s54, s55) or encoded & 0xA0 != original & 0xA0:
                raise ValueError("reviewed forward/inverse field mismatch")
            cases += 1
        fields = list(reviewed_decode(original))
        for value in (0, 1):
            fields[2] = value
            patched = reviewed_encode(original, *fields)
            if patched != (original & ~8) | (value << 3):
                raise ValueError("checkbox alters another field")
    return {"forward_inverse_cases": cases, "byte_round_trips": 256,
            "single_bit_toggle_cases": 512, "result": "PASS",
            "scope": "algebraic cross-check of reviewed instructions; not execution of the GUI or silicon"}


def audit(raw: bytes) -> dict:
    if hashlib.sha256(raw).hexdigest() != GUI_SHA256:
        raise ValueError("unrecognized GUI artifact; do not apply this version-specific audit")
    pe = struct.unpack_from("<I", raw, 0x3C)[0]
    section_count = struct.unpack_from("<H", raw, pe+6)[0]
    optional_size = struct.unpack_from("<H", raw, pe+20)[0]
    base = struct.unpack_from("<I", raw, pe+24+28)[0]
    sections = []
    for index in range(section_count):
        pos = pe+24+optional_size+index*40
        _, address, size, offset = struct.unpack_from("<IIII", raw, pos+8)
        sections.append((address, size, offset))
    for name, (va, expected_hex) in BLOCKS.items():
        expected = bytes.fromhex(expected_hex)
        match = next((raw[offset+va-base-address:offset+va-base-address+len(expected)]
                      for address, size, offset in sections
                      if address <= va-base and va-base+len(expected) <= address+size), None)
        if match != expected:
            raise ValueError(f"{name} instruction signature differs")
    title_offset = 0x1FBDC
    if raw[title_offset:title_offset+44] != "POWER_ONLY_ABOVE_5V  \0".encode("utf-16le"):
        raise ValueError("checkbox title differs")
    if raw[title_offset-8:title_offset] != bytes.fromhex("5c040000ffff8000"):
        raise ValueError("checkbox ID/class differs")
    return {"source": GUI_SOURCE, "sha256": GUI_SHA256, "artifact": "STUSB4500_GUI_1.08.exe",
            "method": "static byte/resource/instruction inspection; GUI not executed",
            "checkbox_id": "0x45C", "configuration_member_offset": "0x54",
            "image_offset": "0x26", "nvm_address": "0xE6", "bit": 3,
            "instruction_blocks_verified": list(BLOCKS), "algebraic_check": check_bijection(),
            "hardware_validated": False, "programming_allowed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.executable.read_bytes()), indent=2))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
