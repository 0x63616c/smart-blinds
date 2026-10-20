"""Guard the narrow compiler-compatibility conversion against hiding changes."""
from pathlib import Path
import tempfile
import unittest

from normalize_placement_pcb import normalize
from kicad_sexpr import children, one, parse


class PlacementFormatTests(unittest.TestCase):
    source='''(kicad_pcb (version 20260206)
      (setup (tenting (front yes) (back yes))
        (covering (front no) (back no)) (plugging (front no) (back no))
        (capping no) (filling no))
\t(footprint "local:part" (property "Reference" "R1")
       (property "atopile_address" "r") (attr smd)
       (pad "1" smd rect (net "A")) (pad "2" smd rect (net "B")))
    )'''
    reference='''(kicad_pcb (version 20241229) (net 4 "A") (net 7 "B")
      (footprint "local:part" (property "Reference" "R1")
       (property "atopile_address" "r") (attr smd)
       (pad "1" smd rect (net 4 "A")) (pad "2" smd rect (net 7 "B"))))'''

    def convert(self,source):
        with tempfile.TemporaryDirectory() as folder:
            ref=Path(folder)/'reference.kicad_pcb';ref.write_text(self.reference)
            return normalize(source,ref)

    def test_reviewed_defaults_and_ids_survive(self):
        board=parse(self.convert(self.source))
        self.assertEqual(str(one(board,'version')[1]),'20241229')
        self.assertEqual([(str(n[1]),n[2]) for n in children(board,'net')],[('4','A'),('7','B')])
        self.assertEqual(one(one(board,'setup'),'tenting')[1:],['front','back'])

    def test_reject_new_net(self):
        with self.assertRaises(ValueError):self.convert(self.source.replace('(net "A")','(net "NEW")'))

    def test_reject_changed_connection(self):
        with self.assertRaises(ValueError):self.convert(self.source.replace('(net "A")','(net "B")'))

    def test_reject_changed_part(self):
        with self.assertRaises(ValueError):self.convert(self.source.replace('local:part','local:other'))

    def test_reject_process_override(self):
        with self.assertRaises(ValueError):self.convert(self.source.replace('(capping no)','(capping yes)'))

    def test_reject_routing(self):
        with self.assertRaises(ValueError):self.convert(self.source.replace('(setup','(via (at 0 0)) (setup'))

    def test_reject_copper_zone(self):
        with self.assertRaises(ValueError):self.convert(self.source.replace('(setup','(zone (net "A")) (setup'))


if __name__=='__main__':unittest.main()
