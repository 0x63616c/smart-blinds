import unittest
from unittest.mock import patch
from max17320 import (REGISTERS, LinuxI2CReader, address, capture, compare_partial,
                      decode_word, derive_partial_profile, signed, telemetry)


class GaugeTests(unittest.TestCase):
    def baseline(self):
        regs = dict.fromkeys(REGISTERS, 0)
        regs.update(DevName=0x420A, nPackCfg=0x0004, nNVCfg0=0x0A00)
        return {"registers": regs}

    def test_address_and_byte_order(self):
        self.assertEqual(address(0x021), (0x36, 0x21))
        self.assertEqual(address(0x1CF), (0x0B, 0xCF))
        self.assertEqual(decode_word(bytes([0x0A, 0x42])), 0x420A)
        for reg in (0x100, 0x17F, 0x200, -1, True):
            with self.assertRaises(ValueError):
                address(reg)
        with self.assertRaises(ValueError):
            decode_word(b"\x42")

    def test_3s2p_capacity_does_not_multiply_by_series(self):
        profile = derive_partial_profile(self.baseline(), series=3, parallel=2,
                                         cell_mah="5000", rsense_milliohm="10")
        self.assertEqual(profile["pack"]["nominal_mah"], "10000")
        self.assertEqual(profile["proposed_registers"]["nFullCapNom"], 0x4E20)
        self.assertEqual(profile["proposed_registers"]["nRSense"], 0x03E8)
        self.assertEqual(profile["proposed_registers"]["nPackCfg"], 0x0005)
        self.assertEqual(profile["proposed_registers"]["nNVCfg0"], 0x0A10)
        self.assertEqual(profile["status"], "INCOMPLETE_DO_NOT_PROGRAM")
        self.assertTrue(profile["unresolved"])

    def test_resistor_scale_changes_capacity_units(self):
        profile = derive_partial_profile(self.baseline(), series=3, parallel=2,
                                         cell_mah="5000", rsense_milliohm="5")
        self.assertEqual(profile["proposed_registers"]["nFullCapNom"], 10000)
        self.assertEqual(profile["proposed_registers"]["nRSense"], 500)

    def test_invalid_or_unrepresentable_profile_rejected(self):
        args = dict(series=3, parallel=2, cell_mah="5000", rsense_milliohm="10")
        for changes in ({"series": 5}, {"parallel": 0}, {"cell_mah": "NaN"},
                        {"rsense_milliohm": "0"}, {"rsense_milliohm": "10.001"},
                        {"cell_mah": "100000"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                derive_partial_profile(self.baseline(), **(args | changes))

    def test_partial_comparison_and_revision_guard(self):
        baseline = self.baseline()
        profile = derive_partial_profile(baseline, series=3, parallel=2,
                                         cell_mah="5000", rsense_milliohm="10")
        self.assertFalse(compare_partial(profile, baseline)["matching"])
        baseline["registers"].update(profile["proposed_registers"])
        self.assertTrue(compare_partial(profile, baseline)["matching"])
        baseline["registers"]["DevName"] = 0x4209
        with self.assertRaisesRegex(ValueError, "DevName"):
            compare_partial(profile, baseline)

    def test_signed_current_temperature_and_unknown_soc(self):
        snapshot = self.baseline()
        snapshot["registers"].update(RepSOC=0x3200, Batt=38400, Current=0xE700,
                                     Temp=0xFB00, Cell1=51200, Cell2=51200, Cell3=51200)
        values = telemetry(snapshot, "10")
        self.assertEqual(values["soc_percent"], 50)
        self.assertAlmostEqual(values["current_a"], -1)
        self.assertEqual(values["temperature_c"], -5)
        self.assertEqual(values["pack_v"], 12)
        self.assertEqual(values["cell_v"], [4, 4, 4])
        snapshot["registers"]["RepSOC"] = 0xFFFF
        self.assertIsNone(telemetry(snapshot, "10")["soc_percent"])
        self.assertEqual(signed(0x8000), -32768)

    def test_missing_device_aborts_capture_not_zero_fill(self):
        class Missing:
            def read_word(self, register):
                raise OSError("NACK")
        with self.assertRaisesRegex(OSError, "NACK"):
            capture(Missing())

    def test_linux_transaction_has_only_pointer_then_read(self):
        def ioctl(fd, operation, transaction):
            self.assertEqual(operation, 0x0707)
            self.assertEqual(transaction.nmsgs, 2)
            pointer, read = transaction.msgs[0], transaction.msgs[1]
            self.assertEqual((pointer.addr, pointer.flags, pointer.len), (0x0B, 0, 1))
            self.assertEqual(pointer.buf[0], 0xCF)
            self.assertEqual((read.addr, read.flags, read.len), (0x0B, 1, 2))
            read.buf[0], read.buf[1] = 0xE8, 0x03
            return 2
        with patch("os.open", return_value=20), patch("os.close"), patch("fcntl.ioctl", side_effect=ioctl):
            with LinuxI2CReader(1) as reader:
                self.assertEqual(reader.read_word(0x1CF), 1000)
                with self.assertRaises(ValueError):
                    reader.read_word(0x060)  # Command register is never accessible.

    def test_linux_short_transfer_is_failure(self):
        with patch("os.open", return_value=20), patch("os.close"), patch("fcntl.ioctl", return_value=1):
            with LinuxI2CReader(1) as reader, self.assertRaises(OSError):
                reader.read_word(0x021)


if __name__ == "__main__":
    unittest.main()
