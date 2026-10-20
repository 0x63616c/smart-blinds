"""Integration regressions use KiCad itself to interpret the real motor schematic."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from generate_schematics import ROOT, board_graph, verify_netlist
from kicad_sexpr import children, dumps, parse


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


if __name__ == "__main__":
    unittest.main()
