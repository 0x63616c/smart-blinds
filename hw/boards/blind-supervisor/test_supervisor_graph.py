"""Regression checks for dangerous compiled-net substitutions."""
import copy
from pathlib import Path
import unittest

from check_supervisor import ROOT, board_graph, verify_graph


class SupervisorGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = board_graph(ROOT / "hw/layouts/blind-supervisor/supervisor-test/supervisor-test.kicad_pcb")

    def component(self, graph, name):
        return next(c for c in graph.values() if c["properties"]["atopile_address"].endswith("."+name))

    def test_all49_physical_pins_match_reviewed_connections(self):
        self.assertEqual(verify_graph(self.graph), 49)

    def test_reject_gate_bypassing_supervisor_reset(self):
        graph = copy.deepcopy(self.graph)
        gate = self.component(graph, "gate")
        gate["pads"]["1"] = gate["pads"]["5"]
        with self.assertRaisesRegex(AssertionError, "pin graph"):
            verify_graph(graph)

    def test_reject_grounding_watchdog_disable_input(self):
        graph = copy.deepcopy(self.graph)
        watchdog = self.component(graph, "watchdog")
        watchdog["pads"]["3"] = watchdog["pads"]["5"]
        with self.assertRaisesRegex(AssertionError, "pin graph"):
            verify_graph(graph)

    def test_reject_disconnected_replacement_gate(self):
        graph = copy.deepcopy(self.graph)
        gate = self.component(graph, "gate")
        gate["pads"] = {p: "unconnected"+p for p in gate["pads"]}
        with self.assertRaisesRegex(AssertionError, "pin graph"):
            verify_graph(graph)


if __name__ == "__main__":
    unittest.main()
