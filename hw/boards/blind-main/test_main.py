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
        result=verify(self.graph)
        self.assertEqual((result['components'],result['physical_pins']),(196,609))

    def test_motor_tail_grounded(self):
        self.change('motor_output.landing1','1','motor.ic','9')

    def test_encoder_channels_swapped(self):
        self.change('encoder_port.header','3','controller.r_b_series','1')

    def test_encoder_port_wrong_rail(self):
        self.change('encoder_port.header','2','logic_supply.ic','3')

    def test_home_reserved_pin_powered(self):
        self.change('home_port.header','2','logic_supply.ic','3')

    def test_home_esd_disconnected(self):
        self.change('home_esd','5','encoder_port.header','3')

    def test_whole_net_cross_block_shorts(self):
        cases=[('motor_output.landing1','1','encoder_port.header','3'),
               ('motor_output.landing1','1','home_port.header','3'),
               ('motor_output.landing1','1','controller.r_dp','2'),
               ('home_port.header','3','usb.pd','8')]
        for first,pin,second,other_pin in cases:
            with self.subTest(first=first,second=second):
                graph=copy.deepcopy(self.graph)
                old=graph[self.refs[first]]['pads'][pin]
                new=graph[self.refs[second]]['pads'][other_pin]
                self.assertNotEqual(old,new)
                for component in graph.values():
                    for number,net in component['pads'].items():
                        if net==old:component['pads'][number]=new
                with self.assertRaisesRegex(AssertionError,'Global net partition'):
                    verify(graph)

    def test_duplicate_address_cannot_hide_component(self):
        graph=copy.deepcopy(self.graph)
        graph['D999']=copy.deepcopy(graph[self.refs['home_esd']])
        graph['D999']['properties']['Reference']='D999'
        with self.assertRaisesRegex(AssertionError,'duplicate component address'):verify(graph)

    def test_missing_address_cannot_hide_component(self):
        graph=copy.deepcopy(self.graph)
        del graph[self.refs['home_esd']]['properties']['atopile_address']
        with self.assertRaisesRegex(AssertionError,'component address'):verify(graph)

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

    def test_charger_pmid_lead_grounded(self):
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
