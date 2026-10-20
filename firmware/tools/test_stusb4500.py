import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import stusb4500 as st
import stusb4500_gui_audit as audit


# ST NVM technical note p19 reference, not a read from the owner's chip.
BASELINE = bytes.fromhex(
    "0000b0aa00450000 10409c1cff013cdf 02400f003200fcf1 "
    "001956aff5355f00 004b9021430040fb")


def gui(raw):
    return "\r\n".join(f"0x{0xC0+i:02X}:\t" + "\t".join(f"0x{b:02X}" for b in raw[i:i+8])
                        for i in range(0, 40, 8)) + "\r\n"


class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.proposal = st.derive(BASELINE)

    def test_manufacturer_reference_decodes(self):
        data = st.decode(BASELINE)
        self.assertEqual([(p["voltage_mv"], p["current_ma"]) for p in data["pdos"]],
                         [(5000, 1500), (15000, 1500), (20000, 1000)])
        self.assertEqual(data["pdo_count"], 3)
        self.assertEqual((data["discharge_to_zero_code"], data["discharge_to_lower_pdo_code"]), (9, 12))

    def test_proposal_documented_bytes_and_derived_gate_bit(self):
        raw = st.image(self.proposal["candidate_hex"])
        self.assertEqual(raw.hex(),
                         "0000b0aa0045000010409c1cff013cdf02400f003200fcf1001957aff9955f00002d2c21430048fb")
        decoded = st.decode(raw)
        self.assertEqual([(p["voltage_mv"], p["current_ma"]) for p in decoded["pdos"]], list(st.PDO_REQUIREMENTS))
        self.assertTrue(decoded["usb_communications_capable"])
        self.assertFalse(decoded["req_src_current"])
        self.assertTrue(decoded["power_only_above_5v"])
        self.assertEqual(raw[0xE6-0xC0], 0x48)
        self.assertFalse(self.proposal["programming_allowed"])

    def test_gui_forward_inverse_and_isolated_bit_change(self):
        self.assertEqual(audit.check_bijection()["forward_inverse_cases"], 16384)
        for value in range(256):
            baseline = bytearray(BASELINE)
            baseline[38] = value
            candidate = st.image(st.derive(bytes(baseline))["candidate_hex"])
            self.assertEqual(candidate[38], (value & ~0x18) | 0x08)
            self.assertTrue(st.decode(candidate)["power_only_above_5v"])
            self.assertFalse(st.decode(candidate)["req_src_current"])
        with self.assertRaises(ValueError):
            audit.audit(b"not the pinned manufacturer artifact")

    def test_reserved_and_unmodified_bits_preserved_exhaustively(self):
        for byte in range(40):
            for bit in range(8):
                baseline = bytearray(BASELINE)
                baseline[byte] ^= 1 << bit
                candidate = st.image(st.derive(bytes(baseline))["candidate_hex"])
                allowed = st.FIELD_MASKS.get(0xC0+byte, 0)
                if byte == 0xCA-0xC0:
                    allowed = 0  # Timers untouched unless explicitly proposed.
                self.assertEqual(candidate[byte] & ~allowed, baseline[byte] & ~allowed)

    def test_timers_explicit_unqualified_and_bounded(self):
        proposal = st.derive(BASELINE, to_zero=15, to_lower_pdo=1)
        self.assertEqual(st.image(proposal["candidate_hex"])[10], 0xF1)
        self.assertIn("UNQUALIFIED", proposal["timer_status"])
        self.assertFalse(proposal["programming_allowed"])
        for bad in (0, 16, -1, True, 1.5, "9"):
            with self.assertRaises(ValueError):
                st.derive(BASELINE, to_zero=bad)

    def test_gui_format_strict(self):
        self.assertEqual(st.parse_gui("// reference only\n"+gui(BASELINE)), BASELINE)
        lines = gui(BASELINE).splitlines()
        for bad in ("\n".join(lines[:-1]), "\n".join(lines+[lines[0]]),
                    gui(BASELINE).replace("0xC0:", "0xC1:"),
                    gui(BASELINE).replace("0xB0", "0x1B0"),
                    gui(BASELINE).replace("0xB0", "__import__('os')")):
            with self.assertRaises(ValueError):
                st.parse_gui(bad)

    def test_bad_hex_and_size(self):
        for bad in ("", "0"*79, "0"*81, "z"*80, None, "00 "*40):
            with self.assertRaises(ValueError):
                st.image(bad)
        for bad in (bytes(39), bytes(41), bytearray(40)):
            with self.assertRaises(ValueError):
                st.decode(bad)

    def test_every_readback_byte_mismatch_detected(self):
        expected = st.image(self.proposal["candidate_hex"])
        for index in range(40):
            bad = bytearray(expected)
            bad[index] ^= 1
            result = st.compare(self.proposal, bytes(bad))
            self.assertFalse(result["matching"])
            self.assertEqual(result["differences"][0]["nvm_address"], f"0x{0xC0+index:02X}")

    def test_matching_readback_cannot_approve(self):
        result = st.compare(self.proposal, st.image(self.proposal["candidate_hex"]))
        self.assertTrue(result["matching"])
        self.assertFalse(result["factory_accepted"])
        self.assertFalse(result["programming_allowed"])

    def test_proposal_tampering_rejected(self):
        for key, value in (("programming_allowed", True), ("status", "APPROVED"),
                           ("candidate_hex", BASELINE.hex()), ("unresolved", []),
                           ("candidate_sha256", "0"*64), ("upstream_commit", "another")):
            altered = copy.deepcopy(self.proposal)
            altered[key] = value
            with self.assertRaises(ValueError):
                st.compare(altered, BASELINE)

    def runtime(self):
        # Independent literal wire words: 5V/1.5A + USB data, 9V/2.5A, 15V/2.5A.
        return {"schema": "smart-blinds/stusb4500-runtime/v1", "device_id": 0x21,
                "pdo_count_register": 3, "pdo_registers_hex": "96900104fad00200fab00400"}

    def test_active_register_readback_and_byte_order(self):
        snap = self.runtime()
        result = st.compare_runtime(self.proposal, snap)
        self.assertTrue(result["matching_checked_fields"])
        self.assertFalse(result["factory_accepted"])
        self.assertFalse(result["power_cycle_proven"])
        snap["pdo_registers_hex"] = "040190960002d0fa0004b0fa"  # Wrong endianness.
        self.assertFalse(st.compare_runtime(self.proposal, snap)["matching_checked_fields"])

    def test_active_pdo_and_flag_mutations(self):
        for bit in (0, 9, 10, 19, 26, 27, 30, 31, 32, 42, 64, 74):
            snap = self.runtime()
            raw = bytearray.fromhex(snap["pdo_registers_hex"])
            raw[bit//8] ^= 1 << (bit % 8)
            snap["pdo_registers_hex"] = raw.hex()
            self.assertFalse(st.compare_runtime(self.proposal, snap)["matching_checked_fields"])
        snap = self.runtime()
        snap["pdo_count_register"] = 2
        self.assertFalse(st.compare_runtime(self.proposal, snap)["matching_checked_fields"])

    def test_runtime_identity_and_length_rejected(self):
        for key, value in (("device_id", 0x20), ("device_id", True),
                           ("pdo_count_register", True), ("pdo_registers_hex", "00"),
                           ("schema", "other")):
            snap = self.runtime()
            snap[key] = value
            with self.assertRaises(ValueError):
                st.compare_runtime(self.proposal, snap)

    def test_read_plan_has_no_erase_program_and_bounded_polling(self):
        plan = st.read_sequence()
        self.assertEqual(plan["i2c_address_7bit"], 0x28)
        opcodes = [op["bytes"] for op in plan["operations"] if op.get("register") == 0x97]
        self.assertEqual(opcodes, [[0]]*5)
        reads = [op for op in plan["operations"] if op["operation"] == "read"]
        self.assertEqual([(op["register"], op["length"], op["sector"]) for op in reads],
                         [(0x53, 8, i) for i in range(5)])
        polls = [op for op in plan["operations"] if op["operation"] == "poll_clear"]
        self.assertEqual(len(polls), 5)
        self.assertTrue(all(op["timeout_ms"] <= 100 and op["max_reads"] <= 100 for op in polls))
        self.assertEqual(plan["finally_attempt_cleanup"][-1],
                         {"operation": "write", "register": 0x95, "bytes": [0]})

    def test_cli_reports_mismatch_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"proposal.json").write_text(json.dumps(self.proposal))
            (root/"readback.txt").write_text(gui(BASELINE))
            result = subprocess.run([sys.executable, st.__file__, "compare", str(root/"proposal.json"),
                                     str(root/"readback.txt")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)["matching"])


if __name__ == "__main__":
    unittest.main()
