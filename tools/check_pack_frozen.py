#!/usr/bin/env python3
"""Frozen circuit validation in an isolated copy, plus final carrier placement.

The canonical PCB includes four board-only NPTH holes. Pinned atopile removes
those because it only owns electrical components. Remove only those reviewed
features in a temporary copy, compile frozen there, and independently check
all features of the final canonical PCB. Canonical inputs are never rewritten.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from kicad_sexpr import parse,dumps
from restore_pack_holes import strip_checked_holes
from generate_schematics import board_graph

ROOT=Path(__file__).resolve().parents[1]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def source_snapshot():
    """Hash the complete read set before copying, including directory membership."""
    paths=[ROOT/p for p in [
        'tools/check_pack_frozen.py','tools/restore_pack_holes.py',
        'tools/generate_schematics.py','tools/kicad_sexpr.py',
        'hw/placement/blind-pack/checks.py','hw/placement/blind-pack/placement.json',
        'hw/sim/blind-pack/checks.py','hw/boards/blind-carrier/carrier-connectivity.json',
        'cad/parameters/retained-interfaces.json']]
    paths.extend(p for p in (ROOT/'hw/parts').rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts)
    for which in ('primary','companion'):
        source=ROOT/f'hw/boards/blind-pack-{which}'
        paths.extend([source/'ato.yaml',*(p for p in source.glob('*.ato') if p.is_file())])
        layout=ROOT/f'hw/layouts/blind-pack-{which}/{which}-test'
        paths.extend([layout/'fp-lib-table',layout/f'{which}-test.kicad_pcb'])
    return {str(p.relative_to(ROOT)):digest(p) for p in sorted(set(paths))}


def check_sources(expected):
    actual=source_snapshot()
    if actual!=expected:
        changed=sorted(k for k in expected.keys()|actual.keys() if expected.get(k)!=actual.get(k))
        raise RuntimeError('Source changed during isolated validation: '+', '.join(changed))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ato',default='ato',help='Path to the pinned atopile 0.15.9 executable')
    p.add_argument('--output',type=Path);a=p.parse_args()
    version=subprocess.run([a.ato,'--version'],capture_output=True,text=True,check=True).stdout.strip()
    if not re.search(r'\b0\.15\.9\b',version):raise ValueError('Expected atopile 0.15.9: '+version)
    sources=source_snapshot()
    spec=importlib.util.spec_from_file_location('placement_checks',ROOT/'hw/placement/blind-pack/checks.py')
    placement=importlib.util.module_from_spec(spec);spec.loader.exec_module(placement)
    plan=json.loads((ROOT/'hw/placement/blind-pack/placement.json').read_text())
    mechanical=json.loads((ROOT/'cad/parameters/retained-interfaces.json').read_text())['carrier']
    paths={w:ROOT/f'hw/layouts/blind-pack-{w}/{w}-test/{w}-test.kicad_pcb' for w in ('primary','companion')}
    original={w:sources[str(path.relative_to(ROOT))] for w,path in paths.items()}
    checked={w:placement.check_board(w,path,plan,mechanical) for w,path in paths.items()}
    results={}
    try:
        with tempfile.TemporaryDirectory(prefix='smart-blinds-circuit-') as folder:
            isolated=Path(folder)
            shutil.copytree(ROOT/'hw/parts',isolated/'hw/parts',ignore=shutil.ignore_patterns('__pycache__'))
            part_inputs={str(p.relative_to(isolated/'hw/parts')):digest(p) for p in sorted((isolated/'hw/parts').rglob('*')) if p.is_file()}
            wanted_parts={k.removeprefix('hw/parts/'):v for k,v in sources.items() if k.startswith('hw/parts/')}
            if part_inputs!=wanted_parts:raise RuntimeError('Copied parts differ from initial source snapshot')
            parts_digest=hashlib.sha256(json.dumps(part_inputs,sort_keys=True).encode()).hexdigest()
            for which,path in paths.items():
                local=isolated/path.relative_to(ROOT);local.parent.mkdir(parents=True)
                data_bytes=path.read_bytes()
                if hashlib.sha256(data_bytes).hexdigest()!=original[which]:
                    raise RuntimeError('Canonical board changed before copying: '+which)
                data=parse(data_bytes.decode());strip_checked_holes(data)
                local.write_text(dumps(data)+'\n')
                shutil.copy2(path.parent/'fp-lib-table',local.parent/'fp-lib-table')
                if digest(local.parent/'fp-lib-table')!=sources[str((path.parent/'fp-lib-table').relative_to(ROOT))]:
                    raise RuntimeError('Copied footprint table differs from initial source snapshot')
                source=ROOT/f'hw/boards/blind-pack-{which}';project=isolated/source.relative_to(ROOT)
                project.mkdir(parents=True)
                inputs={}
                for src in [source/'ato.yaml',*sorted(p for p in source.glob('*.ato') if p.is_file())]:
                    shutil.copy2(src,project/src.name)
                    key=str(src.relative_to(ROOT));inputs[key]=digest(project/src.name)
                    if inputs[key]!=sources.get(key):raise RuntimeError('Copied board source differs from initial snapshot: '+key)
                # The compiler may only read the copied dependencies. There are
                # no symlinks back to canonical sources or layouts.
                before=board_graph(local)
                run=subprocess.run([a.ato,'build','--frozen'],cwd=project,capture_output=True,text=True)
                if run.returncode:
                    raise RuntimeError(f'{which} isolated frozen circuit failed:\n'+run.stdout+'\n'+run.stderr)
                if board_graph(local)!=before:raise ValueError('Frozen build changed circuit graph')
                build=re.search(r'Build ([0-9a-f]{16}): starting worker',run.stdout+run.stderr)
                results[which]={'status':'PASS: isolated circuit-only frozen build',
                    'removed_mechanical_holes_in_copy':4,'electrical_footprints':len(before),
                    'build_id':build[1] if build else None,'canonical_pcb_sha256':original[which],
                    'source_sha256':inputs}
    finally:
        check_sources(sources)
    result={'status':'PASS: isolated frozen circuits and separate full canonical placement checks',
        'atopile':version,'validation_sources_sha256':{k:v for k,v in sources.items() if not k.startswith('hw/parts/')},'copied_parts_tree_sha256':parts_digest,'copied_parts_files':len(part_inputs),'source_snapshot_rechecked':True,'boards':results,'final_placement':checked,
        'limits':['Frozen compilation deliberately excludes only the four reviewed NPTH holes in a temporary copy.',
                  'Final placement checks include those holes, support/RF restrictions and the independent electrical contract.',
                  'This does not route or qualify the pack. KiCad DRC and physical/thermal tests remain separate.']}
    text=json.dumps(result,indent=2)+'\n'
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(text)
    print(text,end='')


if __name__=='__main__':main()
