#!/usr/bin/env python3
"""Compiled connector contract and source evidence; not a powered-system test."""
import argparse,hashlib,json,runpy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from generate_schematics import board_graph
from kicad_sexpr import children,one,parse
HERE=Path(__file__).resolve().parent
EXPECTED={'1':'pack_positive','2':'pack_ground','3':'gauge_sda','4':'gauge_scl','5':'charger_ntc','6':'charger_ntc_return'}

def verify(graph):
 assert len(graph)==1
 part=next(iter(graph.values()))
 assert part['properties']['Partnumber']=='430450600'
 assert part['properties']['LCSC']=='C127367'
 assert part['pads']==EXPECTED

def calculate():
 runpy.run_path(str(ROOT/'hw/parts/blind-connectors/check.py'))
 pcb=ROOT/'hw/layouts/blind-connectors/connector-test/connector-test.kicad_pcb'
 graph=board_graph(pcb);verify(graph)
 # Deliberate reversed/misassigned wiring must fail the independent pin contract.
 mutant=json.loads(json.dumps(graph));p=next(iter(mutant.values()))['pads'];p['1'],p['2']=p['2'],p['1']
 try:verify(mutant)
 except AssertionError:pass
 else:raise AssertionError('Negative control missed swapped power pins')
 fp=children(parse(pcb.read_text()),'footprint')[0]
 src=parse((ROOT/'hw/parts/blind-connectors/CONN-TH_43045-0600.kicad_mod').read_text())
 def geometry(node):
  return sorted((str(p[1]),str(p[2]),str(p[3]),tuple(float(v) for v in one(p,'at')[1:3]),tuple(float(v) for v in one(p,'size')[1:]),float(one(p,'drill')[1])) for p in children(node,'pad'))
 assert geometry(fp)==geometry(src),'Compiled hole geometry differs from audited source'
 inputs=['hw/boards/blind-connectors/connector.ato','hw/boards/blind-connectors/ato.yaml','hw/parts/blind-connectors/430450600.ato','hw/parts/blind-connectors/430450600.kicad_sym','hw/parts/blind-connectors/CONN-TH_43045-0600.kicad_mod']
 return {'status':'PASS: compiled six-pin assignment and physical holes; one swapped-power negative control','parts':1,'pins':6,'pin_assignment':EXPECTED,'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs},'semantic_graph_sha256':hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest(),'raw_board_sha256':hashlib.sha256(pcb.read_bytes()).hexdigest(),'limits':['No routing, powered test or fit acceptance','Harness contact identity must be checked before cell insertion','No raw tap may leave the retained protected cassette']}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--check',action='store_true');args=a.parse_args();text=json.dumps(calculate(),indent=2)+'\n';out=HERE/'results.json'
 if args.check:assert out.read_text()==text,'Connector report stale'
 else:out.write_text(text)
 print(text,end='')
