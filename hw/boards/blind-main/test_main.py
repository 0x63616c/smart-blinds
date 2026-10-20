import copy
from pathlib import Path
import unittest
from check_main import ROOT, board_graph, verify

class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph=board_graph(ROOT/'hw/layouts/blind-main/main-test/main-test.kicad_pcb')
        cls.refs={c['properties']['atopile_address']:ref for ref,c in cls.graph.items()}

    def change(self,name,pin,other,other_pin):
        graph=copy.deepcopy(self.graph)
        graph[self.refs[name]]['pads'][pin]=graph[self.refs[other]]['pads'][other_pin]
        with self.assertRaises(AssertionError):verify(graph)

    def test_captured_boundaries(self):
        self.assertEqual(verify(self.graph)['components'],191)

    def test_swapped_pack_power(self):
        self.change('pack_connector.header','1','charger.ic','10')

    def test_pack_ntc_shorted_to_return(self):
        self.change('pack_connector.header','5','pack_connector.header','6')

    def test_pack_gauge_bus_swapped(self):
        self.change('pack_connector.header','3','charger.ic','14')

    def test_motor_on_charger_sys(self):
        self.change('motor.ic','11','charger.ic','25')

    def test_usb_switch_bypassed(self):
        self.change('charger.ic','8','usb.efuse','5')

    def test_factory_bus_joined_to_host(self):
        self.change('usb.pd','7','charger.ic','14')

    def test_charger_exposed_pad_grounded(self):
        self.change('charger.ic','29','charger.ic','10')

    def test_encoder_reset_bypassed(self):
        self.change('encoder.gate','1','encoder.gate','5')

    def test_thermal_fault_inverted(self):
        self.change('q_thermal_fault','1','regen.thermostat','3')

    def test_thermal_gate_bypassed(self):
        self.change('motor.ic','3','supervision.gate','4')

    def test_wrong_encoder_supply(self):
        self.change('controller.r_a_up','1','logic_supply.ic','3')

if __name__=='__main__':unittest.main()
