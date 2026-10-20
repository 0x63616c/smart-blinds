import copy
from pathlib import Path
import unittest
from check_assembly import ROOT, board_graph, verify


class AssemblyGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = board_graph(ROOT / 'hw/layouts/blind-assembly/controller-test/controller-test.kicad_pcb')

    def component(self, name):
        return next(c for c in self.graph.values() if c['properties']['atopile_address'] == name)

    def test_real_integration(self):
        self.assertEqual(verify(self.graph)['pins'], 207)

    def test_reject_direct_request_to_driver(self):
        self.component('motor.ic')['pads']['3'] = self.component('controller.mcu')['pads']['18']
        with self.assertRaises(AssertionError):
            verify(self.graph)

    def test_reject_reset_disconnection(self):
        self.component('controller.mcu')['pads']['3'] = 'broken-reset'
        with self.assertRaises(AssertionError):
            verify(self.graph)

    def test_reject_replacement_missing_pad_net(self):
        del self.component('controller.up')['pads']['4']
        with self.assertRaises(AssertionError):
            verify(self.graph)


if __name__ == '__main__':
    unittest.main()
