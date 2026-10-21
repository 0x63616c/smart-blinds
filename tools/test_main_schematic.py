"""Fault injection against KiCad's actual exported integrated schematic netlist."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

from generate_main_schematic import ROOT, LAYOUT, OUTPUT, PROJECT, compile_pages, verify_export
from generate_schematics import board_graph, native_cli


class MainSchematicTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads(LAYOUT.read_text())
        cls.graph = board_graph(ROOT / cls.spec['pcb'])
        cls.pages = compile_pages(cls.spec, cls.graph, lambda p: p.read_text())
        cls.temp = tempfile.TemporaryDirectory()
        path = Path(cls.temp.name) / 'actual.xml'
        cli = native_cli()
        subprocess.run([cli, 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(path),
                        str(OUTPUT / (PROJECT + '.kicad_sch'))], check=True, capture_output=True)
        cls.actual = ET.parse(path)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self): self.tree = copy.deepcopy(self.actual)

    def check(self):
        path = Path(self.temp.name) / 'mutant.xml'; self.tree.write(path)
        return verify_export(self.graph, self.spec['net_names'], self.pages, path)

    def nets(self): return self.tree.getroot().find('nets')

    def named(self, name):
        return next(net for net in self.nets() if net.attrib['name'].rsplit('/', 1)[-1] == name)

    def test_actual_export(self): self.assertEqual(self.check(), 649)

    def test_missing_pin(self):
        net = self.named('PACK_SDA'); net.remove(net.find('node'))
        with self.assertRaisesRegex(ValueError, 'partition'): self.check()

    def test_duplicate_pin(self):
        net = self.named('PACK_SDA'); net.append(copy.deepcopy(net.find('node')))
        with self.assertRaisesRegex(ValueError, 'Duplicate'): self.check()

    def test_whole_net_short(self):
        a = self.named('PACK_SDA'); b = self.named('PACK_SCL')
        for pin in list(b): a.append(pin)
        self.nets().remove(b)
        with self.assertRaisesRegex(ValueError, 'partition'): self.check()

    def test_cross_page_break_with_same_displayed_name(self):
        net = self.named('3V3'); other = ET.SubElement(self.nets(), 'net', code='9999', name='/Disconnected/3V3')
        pin = net.find('node'); net.remove(pin); other.append(pin)
        with self.assertRaisesRegex(ValueError, 'partition'): self.check()

    def test_net_mislabel(self):
        self.named('MOTOR_OUT1').set('name', '/wrong_motor_signal')
        with self.assertRaisesRegex(ValueError, 'names differ'): self.check()

    def test_connected_reserved_home_pin(self):
        ref = next(ref for ref,c in self.graph.items() if c['properties']['atopile_address'] == 'home_port.header')
        net = next(net for net in self.nets() if any(p.attrib['ref']==ref and p.attrib['pin']=='2' for p in net))
        target = self.named('3V3')
        for pin in list(net): target.append(pin)
        self.nets().remove(net)
        with self.assertRaisesRegex(ValueError, 'partition'): self.check()

    def test_duplicate_component(self):
        components = self.tree.getroot().find('components')
        components.append(copy.deepcopy(components[0]))
        with self.assertRaisesRegex(ValueError, 'component set'): self.check()

    def test_duplicate_page_component(self):
        spec = copy.deepcopy(self.spec)
        spec['pages'][-1]['components']['controller.mcu'] = spec['pages'][6]['components']['controller.mcu']
        with self.assertRaisesRegex(ValueError, 'more than once'):
            compile_pages(spec, self.graph, lambda p: p.read_text())


if __name__ == '__main__': unittest.main()
