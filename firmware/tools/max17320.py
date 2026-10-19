#!/usr/bin/env python3
"""Read-only MAX17320 diagnostics and offline, INCOMPLETE EZ profile derivation.

No configuration write, unlock, reset, FET-control or NVM-copy operation exists.
The Linux backend has not been exercised against a physical device.
Primary register definitions: ADI MAX17320 datasheet Rev 12, pp78/79/95/98/125/161.
"""
from __future__ import annotations

import argparse
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Protocol


# An explicit read whitelist avoids scanning or accidentally accessing commands.
REGISTERS = {
    "Status": 0x000, "RepCap": 0x005, "RepSOC": 0x006,
    "FullCapRep": 0x010, "VCell": 0x01A, "Temp": 0x01B,
    "Current": 0x01C, "DevName": 0x021, "CommStat": 0x061,
    "ProtAlrt": 0x0AF, "Cell1": 0x0D8, "Cell2": 0x0D7,
    "Cell3": 0x0D6, "Cell4": 0x0D5, "ProtStatus": 0x0D9,
    "Batt": 0x0DA, "PCKP": 0x0DB,
    "nIChgTerm": 0x19C, "nVEmpty": 0x19E, "nFullCapNom": 0x1A5,
    "nBattStatus": 0x1A8, "nFullCapRep": 0x1A9, "nConfig": 0x1B0,
    "nDesignCap": 0x1B3, "nPackCfg": 0x1B5, "nNVCfg0": 0x1B8,
    "nNVCfg1": 0x1B9, "nNVCfg2": 0x1BA, "nThermCfg": 0x1CA,
    "nRSense": 0x1CF, "nUVPrtTh": 0x1D0, "nTPrtTh1": 0x1D1,
    "nTPrtTh3": 0x1D2, "nIPrtTh1": 0x1D3, "nBalTh": 0x1D4,
    "nTPrtTh2": 0x1D5, "nProtMiscTh": 0x1D6, "nProtCfg": 0x1D7,
    "nJEITAC": 0x1D8, "nJEITAV": 0x1D9, "nOVPrtTh": 0x1DA,
    "nStepChg": 0x1DB, "nDelayCfg": 0x1DC, "nODSCTh": 0x1DD,
    "nODSCCfg": 0x1DE, "nProtCfg2": 0x1DF,
}


def word(value: int) -> int:
    if type(value) is not int or not 0 <= value <= 0xFFFF:
        raise ValueError("register must be an unsigned 16-bit integer")
    return value


def address(register: int) -> tuple[int, int]:
    """Convert internal 9-bit address to (7-bit I2C address, pointer byte)."""
    if type(register) is not int:
        raise ValueError("invalid register")
    if 0 <= register <= 0xFF:
        return 0x36, register
    if 0x180 <= register <= 0x1FF:
        return 0x0B, register & 0xFF
    raise ValueError("SBS/reserved register range is outside this reader")


def decode_word(data: bytes) -> int:
    if len(data) != 2:
        raise ValueError("incomplete register read")
    return int.from_bytes(data, "little")


def signed(value: int) -> int:
    value = word(value)
    return value - 0x10000 if value & 0x8000 else value


def positive(value: str | float | int) -> Decimal:
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("positive finite decimal required") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError("positive finite decimal required")
    return result


def exact_word(value: Decimal) -> int:
    if value != value.to_integral_value():
        raise ValueError("value is not exactly representable; review quantization explicitly")
    return word(int(value))


def derive_partial_profile(baseline: dict, *, series: int, parallel: int,
                           cell_mah: str, rsense_milliohm: str) -> dict:
    """Only reviewed arithmetic and bit fields, never a complete protection image."""
    if type(series) is not int or series not in (2, 3, 4):
        raise ValueError("series must be 2, 3 or 4")
    if type(parallel) is not int or not 1 <= parallel <= 16:
        raise ValueError("invalid parallel count")
    regs = baseline["registers"]
    for name in ("DevName", "nPackCfg", "nNVCfg0"):
        word(regs[name])
    capacity = positive(cell_mah) * parallel  # Series changes voltage, not amp-hours.
    rsense = positive(rsense_milliohm)
    # Capacity LSB = 5 microvolt-hours / Rsense; nRSense LSB = 10 microohms.
    cap_word = exact_word(capacity * rsense / Decimal(5))
    sense_word = exact_word(rsense * Decimal(100))
    if not cap_word or not sense_word:
        raise ValueError("zero capacity or sense resistance")
    proposed = {
        "nFullCapNom": cap_word, "nFullCapRep": cap_word, "nDesignCap": cap_word,
        "nRSense": sense_word,
        "nPackCfg": (regs["nPackCfg"] & ~0x0003) | (series - 2),
        # Disable custom X/OCV tables for ROM EZ, enable explicit DesignCap restore.
        "nNVCfg0": (regs["nNVCfg0"] & ~0xC000) | 0x0010,
    }
    return {
        "schema": "smart-blinds/max17320-partial-profile/v1",
        "status": "INCOMPLETE_DO_NOT_PROGRAM", "dev_name_observed": regs["DevName"],
        "pack": {"series": series, "parallel": parallel, "nominal_mah": str(capacity),
                 "rsense_milliohm": str(rsense)},
        "proposed_registers": proposed,
        "unresolved": [
            "Exact DevName silicon revision and complete baseline review",
            "Cell-specific EZ model accuracy and empty/termination settings",
            "Thermistors, charge-pump, balancing and enabled measurement channels",
            "All voltage/current/short-circuit/temperature protection thresholds and delays",
            "Charger coordination, per-cell limits, startup and permanent-failure behavior",
            "NVM restore bits, checksum/revision rules, reserved bits and write-budget audit",
            "Bench readback, voltage/current calibration and protection fault tests",
        ],
    }


def compare_partial(profile: dict, snapshot: dict) -> dict:
    if profile.get("schema") != "smart-blinds/max17320-partial-profile/v1":
        raise ValueError("unsupported partial profile")
    regs = snapshot["registers"]
    if word(regs["DevName"]) != word(profile["dev_name_observed"]):
        raise ValueError("DevName changed; do not reuse a profile across silicon revisions")
    changes = []
    for name, expected in profile["proposed_registers"].items():
        if name not in REGISTERS:
            raise ValueError("unknown register")
        actual = regs.get(name)
        if actual is not None:
            word(actual)
        if actual != word(expected):
            changes.append({"name": name, "actual": actual, "expected": expected})
    return {"scope": "specified partial registers only; not production acceptance",
            "matching": not changes, "differences": changes}


def telemetry(snapshot: dict, rsense_milliohm: str) -> dict:
    regs = snapshot["registers"]
    r_ohm = float(positive(rsense_milliohm)) / 1000
    raw_soc = word(regs["RepSOC"]) / 256
    return {
        "soc_percent": raw_soc if raw_soc <= 100 else None,
        "pack_v": word(regs["Batt"]) * 0.0003125,
        "current_a": signed(regs["Current"]) * 0.0000015625 / r_ohm,
        "temperature_c": signed(regs["Temp"]) / 256,
        "cell_v": [word(regs[f"Cell{i}"]) * 0.000078125 for i in range(1, 4)],
        "protection_status_raw": word(regs["ProtStatus"]),
        "validity": "unverified diagnostic values; not a power-ready decision",
    }


class Reader(Protocol):
    def read_word(self, register: int) -> int: ...


def capture(reader: Reader) -> dict:
    # Abort the entire capture on NACK/short read/error, never substitute zero.
    values = {name: word(reader.read_word(reg)) for name, reg in REGISTERS.items()}
    return {"schema": "smart-blinds/max17320-readback/v1",
            "host_capture_utc": datetime.now(timezone.utc).isoformat(),
            "source": "register reads; shadow RAM is not independently recalled NVM",
            "registers": values}


class LinuxI2CReader(AbstractContextManager):
    """Diagnostic Linux i2c-dev backend; only combined pointer+read transactions."""
    def __init__(self, bus: int):
        import os
        if type(bus) is not int or bus < 0:
            raise ValueError("invalid bus")
        self.fd = os.open(f"/dev/i2c-{bus}", os.O_RDWR)

    def __exit__(self, *args):
        import os
        os.close(self.fd)

    def read_word(self, register: int) -> int:
        import ctypes as c
        import fcntl
        if register not in REGISTERS.values():
            raise ValueError("register not in read whitelist")
        slave, pointer = address(register)

        class Message(c.Structure):
            _fields_ = [("addr", c.c_uint16), ("flags", c.c_uint16),
                        ("len", c.c_uint16), ("buf", c.POINTER(c.c_uint8))]

        class Transfer(c.Structure):
            _fields_ = [("msgs", c.POINTER(Message)), ("nmsgs", c.c_uint32)]

        request, response = (c.c_uint8 * 1)(pointer), (c.c_uint8 * 2)()
        messages = (Message * 2)(Message(slave, 0, 1, request), Message(slave, 1, 2, response))
        transaction = Transfer(messages, 2)
        # I2C_RDWR returns the number of messages transferred. No data word is written.
        if fcntl.ioctl(self.fd, 0x0707, transaction) != 2:
            raise OSError("incomplete combined I2C transaction")
        return decode_word(bytes(response))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    read = sub.add_parser("read", help="Linux register reads only; no configuration changes")
    read.add_argument("--bus", type=int, required=True)
    read.add_argument("--output", type=Path, required=True)
    derive = sub.add_parser("derive", help="offline incomplete profile; cannot program a device")
    derive.add_argument("baseline", type=Path)
    derive.add_argument("--series", type=int, required=True)
    derive.add_argument("--parallel", type=int, required=True)
    derive.add_argument("--cell-mah", required=True)
    derive.add_argument("--rsense-milliohm", required=True)
    compare = sub.add_parser("compare", help="offline partial register comparison")
    compare.add_argument("profile", type=Path)
    compare.add_argument("readback", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "read":
            with LinuxI2CReader(args.bus) as reader:
                result = capture(reader)
            # Exclusive creation preserves previous diagnostic evidence.
            with args.output.open("x") as output:
                json.dump(result, output, indent=2)
                output.write("\n")
            return
        if args.command == "derive":
            result = derive_partial_profile(json.loads(args.baseline.read_text()),
                series=args.series, parallel=args.parallel, cell_mah=args.cell_mah,
                rsense_milliohm=args.rsense_milliohm)
        else:
            result = compare_partial(json.loads(args.profile.read_text()), json.loads(args.readback.read_text()))
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"MAX17320 operation failed: {exc}\n")


if __name__ == "__main__":
    main()
