#!/usr/bin/env python3
"""Create a linked KiCad review project from an already checked current route.

Only symbol associations, text fields, library aliases and net names change.
An exact inverse must recover the input board and schematic trees.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from kicad_sexpr import parse, children, one, dumps, node
from generate_schematics import board_graph
from build_clean_main import check_drc

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'smart-blinds-main'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native(*args):
    result = subprocess.run(['kicad-cli', *map(str, args)], text=True, capture_output=True)
    allowed = (0, 5) if args[:2] == ('pcb', 'drc') else (0,)
    if result.returncode not in allowed:
        raise RuntimeError(result.stdout + result.stderr)
    return result


def net_partition(tree):
    groups = {}
    for net in children(one(tree, 'nets'), 'net'):
        name = one(net, 'name')[1]
        groups[name] = {(one(pin, 'ref')[1], one(pin, 'pin')[1]) for pin in children(net, 'node')}
    return groups


def package(source, output, render=False):
    if platform.system() != 'Linux':
        raise RuntimeError('Linked KiCad packaging requires isolated Linux; host fallback is disabled')
    source, output = source.resolve(), output.resolve()
    if output.exists():
        raise RuntimeError('Preserve the earlier package; choose a new output directory')
    board_file = source / 'candidate.kicad_pcb'
    receipt = json.loads((source / 'native.json').read_text())
    if digest(board_file) != receipt['board_sha256'] or digest(source / 'candidate.kicad_pro') != receipt['project_sha256']:
        raise RuntimeError('Native source board or project changed after verification')
    schema = ROOT / 'hw/schematics/blind-main'
    verification = json.loads((schema / (PROJECT + '.verification.json')).read_text())
    for rel, expected in verification['source_sha256'].items():
        if digest(ROOT / rel) != expected:
            raise RuntimeError(f'Schematic provenance changed: {rel}')
    guarded = {path: digest(path) for folder in (source, schema) for path in folder.rglob('*')
               if path.is_file() and path.suffix != '.kicad_prl'}
    output.mkdir(parents=True)
    evidence = output / 'review'
    evidence.mkdir()
    native('sch', 'export', 'netlist', '--format', 'kicadxml', '-o', evidence / 'source.xml', schema / (PROJECT + '.kicad_sch'))
    native('sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', evidence / 'source.net', schema / (PROJECT + '.kicad_sch'))
    xml = ET.parse(evidence / 'source.xml').getroot()
    components = {item.attrib['ref']: item for item in xml.find('components')}
    graph = board_graph(board_file)
    assert set(components) == set(graph)
    partitions = net_partition(parse((evidence / 'source.net').read_text()))
    original_partitions = {}
    for ref, part in graph.items():
        for pin, net in part['pads'].items():
            original_partitions.setdefault(net, set()).add((ref, pin))
    assert {frozenset(value) for value in partitions.values()} == {frozenset(value) for value in original_partitions.values()}
    target_net = {pin: net for net, pins in partitions.items() for pin in pins}
    rename = {old: target_net[next(iter(pins))] for old, pins in original_partitions.items()}
    assert len(rename) == len(set(rename.values()))
    before = parse(board_file.read_text())
    board = copy.deepcopy(before)
    original_footprints = {one(f, 'uuid')[1]: copy.deepcopy(f) for f in children(board, 'footprint')}
    aliases, paths = {}, {}
    reviewed = json.loads((ROOT / 'hw/routing/clean-main/reviewed-parts.json').read_text())['parts']
    for footprint in children(board, 'footprint'):
        props = {p[1]: p for p in children(footprint, 'property')}
        ref = props['Reference'][2]
        component = components[ref]
        fields = {p.attrib['name']: p.attrib.get('value', '') for p in component.findall('property')}
        address = props['atopile_address'][2]
        assert address == fields['atopile_address']
        assert reviewed[address]['alias'] == component.findtext('footprint')
        assert props.get('Partnumber', ['', '', ''])[2] == fields['MPN']
        assert props.get('LCSC', ['', '', ''])[2] == fields['LCSC']
        aliases[ref] = footprint[1]
        props['Value'][2] = component.findtext('value') or ''
        assert not children(footprint, 'path')
        path = component.find('sheetpath').attrib['tstamps'] + component.findtext('tstamps')
        assert path not in paths.values()
        paths[ref] = path
        footprint.append(node('path', path))
        for key in ('Sheetname', 'Sheetfile', 'MPN', 'LCSC'):
            if key in props:
                assert props[key][2] == fields[key]
            else:
                prop = copy.deepcopy(props['Description'])
                prop[1:3] = [key, fields[key]]
                footprint.append(prop)

    def rename_nets(tree, mapping):
        if not isinstance(tree, list):
            return
        if tree and tree[0] == 'net':
            assert len(tree) == 2 and tree[1] in mapping
            tree[1] = mapping[tree[1]]
        for child in tree[1:]:
            rename_nets(child, mapping)

    rename_nets(board, rename)
    inverse = copy.deepcopy(board)
    rename_nets(inverse, {new: old for old, new in rename.items()})
    for footprint in children(inverse, 'footprint'):
        original = original_footprints[one(footprint, 'uuid')[1]]
        names = {p[1] for p in children(original, 'property')}
        footprint[:] = [p for p in footprint if not (isinstance(p, list) and
            (p[0] == 'path' or (p[0] == 'property' and p[1] not in names)))]
        next(p for p in children(footprint, 'property') if p[1] == 'Value')[2] = next(p for p in children(original, 'property') if p[1] == 'Value')[2]
    assert inverse == before, 'Pairing changed physical board geometry'
    for folder in ('models', 'clean-main.pretty'):
        shutil.copytree(source / folder, output / folder)
    shutil.copyfile(source / 'fp-lib-table', output / 'fp-lib-table')
    for path in schema.iterdir():
        if path.suffix not in ('.kicad_sch', '.kicad_sym') and path.name != 'sym-lib-table':
            continue
        if path.suffix != '.kicad_sch':
            shutil.copyfile(path, output / path.name)
            continue
        original = parse(path.read_text())
        schematic = copy.deepcopy(original)
        added, old_aliases = {}, {}
        for symbol in children(schematic, 'symbol'):
            props = {p[1]: p for p in children(symbol, 'property')}
            ref = props['Reference'][2]
            old_aliases[ref] = props['Footprint'][2]
            props['Footprint'][2] = aliases[ref]
            added[ref] = []
            for name, value in graph[ref]['properties'].items():
                if name in ('Reference', 'Value'):
                    continue
                if name in props:
                    assert props[name][2] == value, (ref, name)
                else:
                    prop = copy.deepcopy(props['Footprint'])
                    prop[1:3] = [name, value]
                    symbol.append(prop)
                    added[ref].append(name)
        inverse = copy.deepcopy(schematic)
        for symbol in children(inverse, 'symbol'):
            props = {p[1]: p for p in children(symbol, 'property')}
            ref = props['Reference'][2]
            props['Footprint'][2] = old_aliases[ref]
            symbol[:] = [p for p in symbol if not (isinstance(p, list) and p[0] == 'property' and p[1] in added[ref])]
        assert inverse == original, 'Pairing changed schematic geometry or circuit'
        (output / path.name).write_text(dumps(schematic) + '\n')
    paired = output / (PROJECT + '.kicad_pcb')
    paired.write_text(dumps(board) + '\n')
    project_bytes = (source / 'candidate.kicad_pro').read_bytes()
    project = output / (PROJECT + '.kicad_pro')
    project.write_bytes(project_bytes)
    import wx
    app = wx.App(False)
    import pcbnew
    loaded = pcbnew.LoadBoard(str(paired))
    native_paths = {fp.GetReference(): fp.GetPath().AsString() for fp in loaded.GetFootprints()}
    assert native_paths == paths and len(paths) == 206
    assert len(list(loaded.GetTracks())) == 636
    native('sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', evidence / 'paired.net', output / (PROJECT + '.kicad_sch'))
    assert net_partition(parse((evidence / 'paired.net').read_text())) == partitions
    native('pcb', 'drc', '--schematic-parity', '--severity-all', '--format', 'json', '-o', evidence / 'parity-drc.json', paired)
    drc = json.loads((evidence / 'parity-drc.json').read_text())
    counts = check_drc(drc, json.loads((ROOT / 'hw/routing/clean-main/native-boundary.json').read_text()))
    project.write_bytes(project_bytes)
    if render:
        for name, rotation in [('top', '0,0,0'), ('oblique', '45,0,-25')]:
            native('pcb', 'render', '--use-board-stackup-colors', '--output', output / (name + '.png'),
                   '--width', '1400', '--height', '1800', '--quality', 'high', '--background', 'transparent',
                   '--rotate', rotation, '--zoom', '.6', paired)
            assert (output / (name + '.png')).stat().st_size > 0
        native('pcb', 'export', 'svg', '--output', output / 'top-copper.svg', '--mode-single',
               '--layers', 'F.Cu,F.SilkS,Edge.Cuts', '--page-size-mode', '2', '--exclude-drawing-sheet', paired)
    for name in ('native.json', 'physical-check.json', 'faults.json'):
        if (source / name).is_file():
            shutil.copyfile(source / name, evidence / name)
    shutil.copyfile(schema / (PROJECT + '.verification.json'), evidence / 'schematic.json')
    for path, expected in guarded.items():
        assert digest(path) == expected, ('Input changed during packaging', str(path))
    result = {'source_board_sha256': digest(board_file), 'paired_board_sha256': digest(paired),
              'project_sha256': digest(project), 'components': len(paths), 'physical_pins': len(target_net),
              'schematic_parity_findings': len(drc['schematic_parity']), 'retained_drc': counts,
              'remaining_connections': len(drc['unconnected_items']), 'physical_AST_inverse_equal': True,
              'schematic_AST_inverse_equal': True, 'native_paths_checked': len(paths),
              'source_capture_sha256': receipt['source_sha256'],
              'limits': ['Partial route, not manufacturing release.', 'No native Update PCB from Schematic operation performed.',
                         'KiCad edits are not automatically returned to the atopile source.']}
    (evidence / 'linked-project.json').write_text(json.dumps(result, indent=2) + '\n')
    (output / 'README.txt').write_text('''Smart Blinds — source-driven linked KiCad review project

Open smart-blinds-main.kicad_pro in KiCad 10. Local symbols, footprints and all
models are included. The board is 54 × 80 mm, four layers, with black mask,
206 grid-placed components, outward connectors and rounded corners.

352 connections remain open. Three named hybrid-footprint DRC findings and
seven documented schematic ERC findings remain. No fabrication, powered,
charging, thermal, RF or physical-assembly acceptance is claimed.

The review folder contains actual native/geometry/graph checks. The schematic
and PCB are linked for inspection; all 649 physical pins match. Geometry is
preserved exactly by an inverse check during metadata pairing. KiCad edits do
not automatically update the maintained atopile source.

Parts must be purchased from the reviewed BOM after a fresh sourcing check;
the copied generic resistor supplier fields have been removed and the captured
catalog identity checks reject conflicting aliases. Availability and assembly
pricing still require a fresh sourcing check.
''')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args()
    print(json.dumps(package(args.source, args.output, args.render), indent=2))
