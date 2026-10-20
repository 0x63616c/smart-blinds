"""Integration regressions use KiCad itself to interpret the circuit drawings."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from generate_schematics import ROOT, board_graph, verify_netlist
from kicad_sexpr import children, dumps, parse


class MechanicalFeatureGraphTests(unittest.TestCase):
    def inspect(self, footprint):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.kicad_pcb'
            path.write_text('(kicad_pcb '+footprint+')')
            return board_graph(path)

    hole='''(footprint "MountingHole_M3_3.4mm"
        (property "Reference" "H1")
        (attr board_only exclude_from_bom exclude_from_pos_files)
        (pad "" np_thru_hole circle (at 0 0) (size 3.4 3.4) (drill 3.4)
             (layers "*.Cu" "*.Mask")))'''

    def test_explicit_isolated_mechanical_hole_omitted(self):
        self.assertEqual(self.inspect(self.hole),{})

    def test_numbered_hole_cannot_hide_electrical_pin(self):
        with self.assertRaises(ValueError):
            self.inspect(self.hole.replace('pad ""','pad "1"'))

    def test_plated_hole_cannot_hide_electrical_pin(self):
        with self.assertRaises(ValueError):
            self.inspect(self.hole.replace('np_thru_hole','thru_hole'))

    def test_net_cannot_hide_in_mechanical_feature(self):
        with self.assertRaises(ValueError):
            self.inspect(self.hole.replace('(at 0 0)','(net 1 "GND") (at 0 0)'))

    def test_atopile_part_cannot_be_silently_omitted(self):
        with self.assertRaises(ValueError):
            self.inspect(self.hole.replace('(attr','(property "atopile_address" "circuit.part") (attr'))

    def test_purchased_hole_must_not_be_silently_omitted(self):
        with self.assertRaises(ValueError):
            self.inspect(self.hole.replace('exclude_from_bom',''))

    def test_absent_board_only_tag_preserves_component(self):
        self.assertIn('H1',self.inspect(self.hole.replace('board_only','')))

    def test_oversized_npth_land_cannot_hide_copper(self):
        with self.assertRaisesRegex(ValueError,'conductive pad geometry'):
            self.inspect(self.hole.replace('(size 3.4 3.4)','(size 4.4 4.4)'))

    def test_copper_graphic_cannot_hide_in_mechanical_feature(self):
        with self.assertRaisesRegex(ValueError,'copper graphics'):
            self.inspect(self.hole.replace('(attr','(fp_line (start 0 0) (end 2 0) (layer "F.Cu")) (attr'))

    def test_offset_drill_not_accepted_as_copper_free(self):
        with self.assertRaisesRegex(ValueError,'pad geometry'):
            self.inspect(self.hole.replace('(drill 3.4)','(drill 3.4 (offset 0.5 0))'))


class NativeSchematicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / "hw/schematics/blind-controller/motor-test.layout.json").read_text())
        cls.graph = board_graph(ROOT / cls.spec["pcb"])
        cls.source = parse((ROOT / cls.spec["output"]).read_text())
        cls.cli = shutil.which("kicad-cli") or "/Applications/KiCad.app/Contents/MacOS/kicad-cli"

    def check(self, schematic, graph=None):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / "motor-test.kicad_sch"
            source.write_text(dumps(schematic))
            subprocess.run([self.cli, "sch", "export", "netlist", "--format", "kicadxml", "-o",
                            str(folder / "net.xml"), str(source)], check=True, capture_output=True)
            return verify_netlist(graph or self.graph, self.spec, folder / "net.xml")

    def test_real_graph_roundtrip(self):
        self.assertEqual(self.check(self.source), 43)

    def test_reject_short_between_direction_inputs(self):
        changed = copy.deepcopy(self.source)
        for label in children(changed, "label"):
            if label[1] == "MOTOR_IN1":
                label[1] = "MOTOR_IN2"
                break
        with self.assertRaisesRegex(ValueError, "graph mismatch"):
            self.check(changed)

    def test_reject_missing_bulk_capacitor(self):
        changed = copy.deepcopy(self.source)
        for symbol in children(changed, "symbol"):
            props = {p[1]: p[2] for p in children(symbol, "property")}
            if props.get("Reference") == "C1":
                changed.remove(symbol)
                break
        with self.assertRaisesRegex(ValueError, "graph mismatch"):
            self.check(changed)

    def test_reject_connected_pcb_pin_marked_nc(self):
        graph = copy.deepcopy(self.graph)
        graph["U1"]["pads"]["7"] = graph["U1"]["pads"]["15"]
        with self.assertRaisesRegex(ValueError, "NC is connected in the PCB"):
            self.check(self.source, graph)


class SupervisorSchematicTests(unittest.TestCase):
    check = NativeSchematicTests.check
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / "hw/schematics/blind-supervisor/supervisor-test.layout.json").read_text())
        cls.graph = board_graph(ROOT / cls.spec["pcb"])
        cls.source = parse((ROOT / cls.spec["output"]).read_text())
        cls.cli = shutil.which("kicad-cli") or "/Applications/KiCad.app/Contents/MacOS/kicad-cli"

    def test_real_graph_roundtrip(self):
        # Includes vertical capacitor and exposed-pad pins; inward-facing wire
        # extensions would short the timing capacitor or cross the IC body.
        self.assertEqual(self.check(self.source), 49)

    def test_reject_timing_capacitor_short(self):
        changed = copy.deepcopy(self.source)
        for label in children(changed, "label"):
            if label[1] == "TIMING":
                label[1] = "GND"
                break
        with self.assertRaisesRegex(ValueError, "graph mismatch"):
            self.check(changed)

    def test_reject_missing_timing_capacitor(self):
        changed = copy.deepcopy(self.source)
        for symbol in children(changed, "symbol"):
            props = {p[1]: p[2] for p in children(symbol, "property")}
            if props.get("Reference") == "C4":
                changed.remove(symbol)
                break
        with self.assertRaisesRegex(ValueError, "graph mismatch"):
            self.check(changed)

    def test_reject_connected_pcb_pin_marked_nc(self):
        graph = copy.deepcopy(self.graph)
        graph["U4"]["pads"]["4"] = graph["U4"]["pads"]["5"]
        with self.assertRaisesRegex(ValueError, "NC is connected in the PCB"):
            self.check(self.source, graph)


class ChargerSchematicTests(unittest.TestCase):
    check = NativeSchematicTests.check

    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / "hw/schematics/blind-charger/charger-test.layout.json").read_text())
        cls.graph = board_graph(ROOT / cls.spec["pcb"])
        cls.source = parse((ROOT / cls.spec["output"]).read_text())
        cls.cli = shutil.which("kicad-cli") or "/Applications/KiCad.app/Contents/MacOS/kicad-cli"

    def test_real_graph_roundtrip(self):
        self.assertEqual(self.check(self.source), 101)

    def test_reject_grounded_exposed_pmid_pad(self):
        changed = copy.deepcopy(self.source)
        for label in children(changed, "label"):
            if label[1] == "PMID":
                label[1] = "GND"
                break
        with self.assertRaisesRegex(ValueError, "graph mismatch"):
            self.check(changed)


class RegulatorSchematicTests(unittest.TestCase):
    check = NativeSchematicTests.check

    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / "hw/schematics/blind-regulator/regulator-test.layout.json").read_text())
        cls.graph = board_graph(ROOT / cls.spec["pcb"])
        cls.source = parse((ROOT / cls.spec["output"]).read_text())
        cls.cli = shutil.which("kicad-cli") or "/Applications/KiCad.app/Contents/MacOS/kicad-cli"

    def test_real_graph_roundtrip(self):
        self.assertEqual(self.check(self.source), 31)

    def test_reject_connected_voltage_selection_pin(self):
        graph = copy.deepcopy(self.graph)
        graph["U1"]["pads"]["9"] = graph["U1"]["pads"]["4"]
        with self.assertRaisesRegex(ValueError, "NC is connected in the PCB"):
            self.check(self.source, graph)


class UsbSchematicTests(unittest.TestCase):
    check = NativeSchematicTests.check

    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / "hw/schematics/blind-usb/usb-test.layout.json").read_text())
        cls.graph = board_graph(ROOT / cls.spec["pcb"])
        cls.source = parse((ROOT / cls.spec["output"]).read_text())
        cls.cli = shutil.which("kicad-cli") or "/Applications/KiCad.app/Contents/MacOS/kicad-cli"

    def test_real_graph_roundtrip(self):
        self.assertEqual(self.check(self.source), 113)

    def test_reject_bypassed_efuse(self):
        changed = copy.deepcopy(self.source)
        for label in children(changed, "label"):
            if label[1] == "OUTPUT":
                label[1] = "RAW"
        with self.assertRaisesRegex(ValueError, "graph mismatch"):
            self.check(changed)

    def test_reject_short_between_cc_channels(self):
        changed = copy.deepcopy(self.source)
        for label in children(changed, "label"):
            if label[1] == "CC2":
                label[1] = "CC1"
                break
        with self.assertRaisesRegex(ValueError, "graph mismatch"):
            self.check(changed)


class CarrierSchematicTests(unittest.TestCase):
    check = NativeSchematicTests.check

    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / "hw/schematics/blind-carrier/carrier-test.layout.json").read_text())
        cls.graph = board_graph(ROOT / cls.spec["pcb"])
        cls.source = parse((ROOT / cls.spec["output"]).read_text())
        cls.cli = shutil.which("kicad-cli") or "/Applications/KiCad.app/Contents/MacOS/kicad-cli"

    def test_real_graph_roundtrip(self):
        self.assertEqual(self.check(self.source), 103)

    def test_reject_wrong_three_cell_sense_connection(self):
        changed = copy.deepcopy(self.source)
        for label in children(changed, "label"):
            if label[1] == "CELL1":
                label[1] = "CELL3"
                break
        with self.assertRaisesRegex(ValueError, "graph mismatch"):
            self.check(changed)

    def test_reject_bypassed_cell_branch_fuse(self):
        changed = copy.deepcopy(self.source)
        for label in children(changed, "label"):
            if label[1] == "CELL1A_POS":
                label[1] = "JUNCTION1"
                break
        with self.assertRaisesRegex(ValueError, "graph mismatch"):
            self.check(changed)

    def test_reject_bypassed_current_shunt(self):
        changed = copy.deepcopy(self.source)
        for label in children(changed, "label"):
            if label[1] == "PACK_GND":
                label[1] = "RAW_GND"
        with self.assertRaisesRegex(ValueError, "graph mismatch"):
            self.check(changed)


class RegenSchematicTests(unittest.TestCase):
    check = NativeSchematicTests.check

    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / "hw/schematics/blind-regen/regen-test.layout.json").read_text())
        cls.graph = board_graph(ROOT / cls.spec["pcb"])
        cls.source = parse((ROOT / cls.spec["output"]).read_text())
        cls.cli = shutil.which("kicad-cli") or "/Applications/KiCad.app/Contents/MacOS/kicad-cli"

    def test_real_graph_roundtrip(self):
        self.assertEqual(self.check(self.source), 105)

    def test_reject_thermal_gate_bypassed(self):
        changed = copy.deepcopy(self.source)
        for label in children(changed, "label"):
            if label[1] == "THERMAL_GATE":
                label[1] = "PACK"
        with self.assertRaisesRegex(ValueError, "graph mismatch"):
            self.check(changed)

    def test_reject_dump_midpoint_short(self):
        changed = copy.deepcopy(self.source)
        for label in children(changed, "label"):
            if label[1] == "SERIES_MID":
                label[1] = "GND"
                break
        with self.assertRaisesRegex(ValueError, "graph mismatch"):
            self.check(changed)


if __name__ == "__main__":
    unittest.main()
