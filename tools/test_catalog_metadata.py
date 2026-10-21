#!/usr/bin/env python3
"""Catalog identity regressions. Pure parsing; no CAD or source mutation."""
from pathlib import Path
import importlib.util
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from kicad_sexpr import parse,children
from generate_schematics import board_graph

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

wrappers=module('catalog_test_wrappers',ROOT/'hw/parts/blind-control-io/make_wrappers.py')
bom=module('catalog_test_bom',ROOT/'bom/captured_components.py')

class CatalogMetadataTests(unittest.TestCase):
    def test_shared_geometry_has_no_supplier_override(self):
        for relative in ('R0402.kicad_mod','blind-control-io.pretty/R0402.kicad_mod'):
            t=parse((ROOT/'hw/parts/blind-control-io'/relative).read_text())
            self.assertNotIn('LCSC Part',{p[1] for p in children(t,'property')})
    def test_generator_removes_multiline_field_only(self):
        text='(footprint "R0402" (property\n "LCSC Part"\t"C11702" (at 0 0)) (property "Reference" "R") (pad "1" smd rect (at -0.5 0) (size 0.5 0.5)))'
        expected=wrappers.sx.loads(text)
        expected[:]=[p for p in expected if not (isinstance(p,list) and str(p[0])=='property' and p[1]=='LCSC Part')]
        actual=wrappers.strip_shared_catalog_property(text)
        self.assertEqual(expected,wrappers.sx.loads(actual))
        self.assertEqual(wrappers.sx.loads(actual),wrappers.sx.loads(wrappers.strip_shared_catalog_property(actual)))
    def test_exact_and_absent_aliases(self):
        for code in ('C11702','C25741','C25900','C25092'):
            for alias in ('',code):
                self.assertEqual(bom.component_catalog({'LCSC':code,'Partnumber':'exact','lcsc_id':code,'LCSC Part':alias},'test'),(code,'exact'))
    def test_wrong_aliases_fail_independently(self):
        for name in ('lcsc_id','LCSC Part'):
            p={'LCSC':'C25741','Partnumber':'0402WGF1003TCE','lcsc_id':'C25741','LCSC Part':'C25741'}
            p[name]='C11702'
            with self.assertRaisesRegex(ValueError,'Conflicting supplier alias'):bom.component_catalog(p,'R41')
    def test_all_captured_purchased_aliases(self):
        for name,relative in bom.BOARDS.items():
            for ref,c in board_graph(ROOT/relative).items():
                if 'exclude_from_bom' not in c['attributes']:
                    bom.component_catalog(c['properties'],f'{name}/{ref}')
    def test_all_shared_resistor_capture_instances(self):
        for path in (ROOT/'hw/layouts').rglob('*.kicad_pcb'):
            for f in children(parse(path.read_text()),'footprint'):
                if f[1]=='blind-control-io:R0402':
                    self.assertNotIn('LCSC Part',{p[1] for p in children(f,'property')},str(path))
    def test_captured_catalog_matches_dated_mpn_evidence(self):
        self.assertIn('bom/captured-components.csv',bom.build())

if __name__=='__main__':unittest.main(verbosity=2)
