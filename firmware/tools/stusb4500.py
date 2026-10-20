#!/usr/bin/env python3
"""Offline STUSB4500 factory proposal and readback checks. No hardware backend.

NVM fields: ST's 39-page NVM technical note, pp22/25-28. Programming
sequence: usb-c/STUSB4500 55d1109e7ef0cffc2ffef2494095d23306594601.
POWER_ONLY_ABOVE_5V mapping and discharge timing are unresolved: every
proposal remains INCOMPLETE_DO_NOT_PROGRAM, including matching readback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

SCHEMA = "smart-blinds/stusb4500-proposal/v1"
UPSTREAM_COMMIT = "55d1109e7ef0cffc2ffef2494095d23306594601"
PDO_REQUIREMENTS = ((5000, 1500), (9000, 2500), (15000, 2500))
CURRENT_LUT_MA = (None, 500, 750, 1000, 1250, 1500, 1750, 2000,
                  2250, 2500, 2750, 3000, 3500, 4000, 4500, 5000)
# Deliberately no mapping for POWER_ONLY_ABOVE_5V. ST's note says E6[3:0]
# reserved; a forum experiment is not accepted as manufacturer approval.
FIELD_MASKS = {0xC9: 0x20, 0xCA: 0xFF, 0xDA: 0xFF, 0xDC: 0x0F,
               0xDD: 0xF0, 0xE0: 0xC0, 0xE1: 0xFF, 0xE2: 0xFF,
               0xE3: 0x03, 0xE6: 0x10}
UNRESOLVED = [
    "POWER_ONLY_ABOVE_5V=1 needs manufacturer/controlled GUI field evidence; preserved bits do not prove it",
    "Discharge timer choices require measured raw/output discharge with actual load, capacitance and reverse paths",
    "Baseline reserved bits, silicon revision and voltage-monitor thresholds require qualified fixture review",
    "Full NVM readback, reset/power-cycle reload and contract-loss/input-path tests have not run on hardware",
]


def image(value: str) -> bytes:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-fA-F]{80}", value) is None:
        raise ValueError("NVM image must be exactly 40 bytes encoded as 80 hex digits")
    return bytes.fromhex(value)


def parse_gui(text: str) -> bytes:
    """Strict ST five-row text format; never evaluate C or accept missing rows."""
    rows = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "//")):
            continue
        match = re.fullmatch(r"(0x[0-9a-fA-F]{2}):\s+(.+)", line)
        if not match:
            raise ValueError("invalid NVM row")
        address = int(match[1], 16)
        tokens = match[2].split()
        if address not in range(0xC0, 0xE8, 8) or address in rows or len(tokens) != 8:
            raise ValueError("duplicate, unknown or incomplete NVM row")
        if any(re.fullmatch(r"0x[0-9a-fA-F]{2}", token) is None for token in tokens):
            raise ValueError("invalid NVM byte")
        rows[address] = bytes(int(token, 16) for token in tokens)
    if len(rows) != 5:
        raise ValueError("all five NVM rows required")
    return b"".join(rows[address] for address in range(0xC0, 0xE8, 8))


def decode(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or len(raw) != 40:
        raise ValueError("exactly 40 NVM bytes required")
    at = lambda address: raw[address - 0xC0]
    flexible_ma = ((at(0xE3) >> 2) | ((at(0xE4) & 15) << 6)) * 10
    indices = (at(0xDA) >> 4, at(0xDC) & 15, at(0xDD) >> 4)
    currents = [CURRENT_LUT_MA[i] if i else flexible_ma for i in indices]
    volts = [5000, ((at(0xE1) << 2) | (at(0xE0) >> 6)) * 50,
             (at(0xE2) | ((at(0xE3) & 3) << 8)) * 50]
    return {
        "pdo_count": (at(0xDA) >> 1) & 3,
        "pdos": [{"voltage_mv": v, "current_ma": c} for v, c in zip(volts, currents)],
        "usb_communications_capable": bool(at(0xDA) & 1),
        "unconstrained_power": bool(at(0xDA) & 8),
        "req_src_current": bool(at(0xE6) & 16),
        "automatic_discharge_enabled": not bool(at(0xC9) & 32),
        "discharge_to_zero_code": at(0xCA) >> 4,
        "discharge_to_lower_pdo_code": at(0xCA) & 15,
        "power_only_above_5v": None,
    }


def timer(value: int | None) -> int | None:
    if value is not None and (type(value) is not int or not 1 <= value <= 15):
        raise ValueError("timer coefficient must be an integer 1..15")
    return value


def derive(baseline: bytes, *, to_zero: int | None = None,
           to_lower_pdo: int | None = None) -> dict:
    """Patch documented fields only; preserve every other baseline bit."""
    decode(baseline)
    to_zero, to_lower_pdo = timer(to_zero), timer(to_lower_pdo)
    raw = bytearray(baseline)

    def field(address: int, mask: int, value: int):
        assert mask & ~FIELD_MASKS[address] == 0 and value & ~mask == 0
        raw[address - 0xC0] = (raw[address - 0xC0] & ~mask) | value

    # Native C6 USB is routed on the board: declare USB data capability.
    field(0xDA, 0xFF, (5 << 4) | (3 << 1) | 1)  # 1.5 A, 3 PDOs, constrained sink.
    field(0xDC, 0x0F, 9)  # 2.5 A lookup, preserve PDO2 low monitor shift.
    field(0xDD, 0xF0, 9 << 4)  # 2.5 A lookup, preserve PDO2 high shift.
    pdo2, pdo3 = 9000 // 50, 15000 // 50
    field(0xE0, 0xC0, (pdo2 & 3) << 6)
    field(0xE1, 0xFF, pdo2 >> 2)
    field(0xE2, 0xFF, pdo3 & 255)
    field(0xE3, 0x03, pdo3 >> 8)  # Preserve unused flexible-current definition.
    field(0xE6, 0x10, 0)  # Request sink current, not source's entire capability.
    field(0xC9, 0x20, 0)  # Automatic discharge enabled, not forced discharge.
    if to_zero is not None:
        field(0xCA, 0xF0, to_zero << 4)
    if to_lower_pdo is not None:
        field(0xCA, 0x0F, to_lower_pdo)
    candidate = bytes(raw)
    return {
        "schema": SCHEMA, "status": "INCOMPLETE_DO_NOT_PROGRAM",
        "programming_allowed": False, "upstream_commit": UPSTREAM_COMMIT,
        "baseline_sha256": hashlib.sha256(baseline).hexdigest(),
        "baseline_hex": baseline.hex(), "candidate_hex": candidate.hex(),
        "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
        "decoded_documented_fields": decode(candidate),
        "required_power_only_above_5v": True,
        "timer_status": "UNQUALIFIED: preserved or explicitly proposed coefficients only",
        "timer_overrides": {"to_zero": to_zero, "to_lower_pdo": to_lower_pdo},
        "changes": [{"nvm_address": f"0x{0xC0+i:02X}", "before": a, "after": b}
                    for i, (a, b) in enumerate(zip(baseline, candidate)) if a != b],
        "unresolved": list(UNRESOLVED),
    }


def validate_proposal(proposal: dict) -> bytes:
    if proposal.get("schema") != SCHEMA or proposal.get("status") != "INCOMPLETE_DO_NOT_PROGRAM" or proposal.get("programming_allowed") is not False:
        raise ValueError("unsupported or falsely approved proposal")
    baseline = image(proposal["baseline_hex"])
    overrides = proposal["timer_overrides"]
    expected = derive(baseline, to_zero=overrides["to_zero"], to_lower_pdo=overrides["to_lower_pdo"])
    # Recompute the entire record: caller-modified hashes/decoded values/approvals
    # cannot launder a different image into the readback report.
    if proposal != expected:
        raise ValueError("proposal differs from the documented generator")
    return image(proposal["candidate_hex"])


def compare(proposal: dict, readback: bytes) -> dict:
    expected = validate_proposal(proposal)
    decode(readback)
    differences = [{"nvm_address": f"0x{0xC0+i:02X}", "expected": a, "actual": b}
                   for i, (a, b) in enumerate(zip(expected, readback)) if a != b]
    return {"scope": "all 40 NVM bytes; not active-register reload or hardware acceptance",
            "matching": not differences, "differences": differences,
            "programming_allowed": False, "factory_accepted": False,
            "unresolved": list(UNRESOLVED)}


def compare_runtime(proposal: dict, snapshot: dict) -> dict:
    """Validate offline post-reset captures from the fixture, not just shadow NVM.

    Runtime byte order/addresses are UM2650 sections3.60-72. PDO fixed fields
    are ST firmware USB_PD_SNK_PDO_TypeDef. This is not live RDO evidence.
    """
    validate_proposal(proposal)
    if snapshot.get("schema") != "smart-blinds/stusb4500-runtime/v1":
        raise ValueError("unsupported runtime snapshot")
    if snapshot.get("device_id") not in (0x21, 0x25) or type(snapshot.get("device_id")) is not int:
        raise ValueError("unsupported silicon ID; fixture review required")
    count = snapshot.get("pdo_count_register")
    if type(count) is not int or not 0 <= count <= 255:
        raise ValueError("invalid count register")
    raw_hex = snapshot.get("pdo_registers_hex")
    if not isinstance(raw_hex, str) or re.fullmatch(r"[0-9a-fA-F]{24}", raw_hex) is None:
        raise ValueError("exactly 12 PDO bytes from 0x85..0x90 required")
    raw = bytes.fromhex(raw_hex)
    differences = []
    if count & 7 != 3:
        differences.append("active PDO count differs")
    for index, (mv, ma) in enumerate(PDO_REQUIREMENTS):
        actual = int.from_bytes(raw[index*4:index*4+4], "little")
        mask = 0xC00FFFFF  # Fixed supply type + voltage + current.
        expected = ((mv // 50) << 10) | (ma // 10)
        if index == 0:
            mask |= 0x0C000000  # USB communication + unconstrained power.
            expected |= 0x04000000
        if actual & mask != expected:
            differences.append(f"active PDO{index+1} differs in checked fields")
    return {"matching_checked_fields": not differences, "differences": differences,
            "scope": "PDO count/type/voltage/current and PDO1 USB/power flags only",
            "power_cycle_proven": False, "factory_accepted": False,
            "note": "A file cannot prove a physical power cycle; NVM gate/discharge/contract tests remain separate"}


def read_sequence() -> dict:
    """Inspectable, bounded abstract plan. There is intentionally no executor.

    ST source uses C0/D0 with FTP_CUST_PWR even though an older technical
    note calls that bit unused. Follow the pinned executable source. Read
    access writes control registers, but never sends erase/program opcodes.
    """
    write = lambda reg, data: {"operation": "write", "register": reg, "bytes": data}
    ops = [write(0x95, [0x47]), write(0x96, [0]), write(0x96, [0xC0])]
    for sector in range(5):
        ops.extend([write(0x96, [0xC0]), write(0x97, [0]),
                    write(0x96, [0xD0 | sector]),
                    {"operation": "poll_clear", "register": 0x96, "mask": 0x10,
                     "timeout_ms": 100, "max_reads": 100},
                    {"operation": "read", "register": 0x53, "length": 8, "sector": sector},
                    write(0x96, [0])])
    cleanup = [write(0x96, [0x40, 0]), write(0x95, [0])]
    return {"status": "OFFLINE_PLAN_NO_EXECUTOR", "i2c_address_7bit": 0x28,
            "per_transfer_timeout_ms": 10, "total_budget_ms": 1000,
            "deadline_note": "fixture abort policies, not measured IC operation guarantees",
            "operations": ops, "finally_attempt_cleanup": cleanup,
            "on_failure": "abort capture, retain hardware inhibit, bounded cleanup, require fixture reset/recovery"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("propose", help="patch an offline ST five-row baseline; never approve programming")
    generate.add_argument("baseline", type=Path)
    generate.add_argument("--to-zero", type=int)
    generate.add_argument("--to-lower-pdo", type=int)
    check = sub.add_parser("compare", help="compare a proposal with offline five-row NVM readback")
    check.add_argument("proposal", type=Path)
    check.add_argument("readback", type=Path)
    runtime = sub.add_parser("compare-runtime", help="check a fixture's offline active PDO capture")
    runtime.add_argument("proposal", type=Path)
    runtime.add_argument("snapshot", type=Path)
    sub.add_parser("read-plan", help="print the bounded abstract NVM-read sequence; no I2C access")
    args = parser.parse_args()
    try:
        if args.command == "propose":
            result = derive(parse_gui(args.baseline.read_text()), to_zero=args.to_zero, to_lower_pdo=args.to_lower_pdo)
        elif args.command == "compare":
            result = compare(json.loads(args.proposal.read_text()), parse_gui(args.readback.read_text()))
        elif args.command == "compare-runtime":
            result = compare_runtime(json.loads(args.proposal.read_text()), json.loads(args.snapshot.read_text()))
        else:
            result = read_sequence()
        print(json.dumps(result, indent=2))
        return 0 if result.get("matching", result.get("matching_checked_fields", True)) else 1
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
