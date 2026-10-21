#!/usr/bin/env python3
"""Build the complete native controller hierarchy; verify all pins via KiCad export."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from generate_schematics import ROOT, board_graph, fx, uid, xy, native_cli
from kicad_sexpr import Atom, children, dumps, node as n, one, parse
from main_schematic_page import draw_page

sys.path.insert(0, str(ROOT / 'hw/boards/blind-main'))
from check_main import verify as verify_integrated

LAYOUT = ROOT / 'hw/schematics/blind-main/main.layout.json'
OUTPUT = ROOT / 'hw/schematics/blind-main'
PROJECT = 'smart-blinds-main'


def compile_pages(spec, graph, read_source):
    """Map preserved block drawing addresses to current refs, without deriving wiring."""
    by_address = {}
    for ref, c in graph.items():
        a = c['properties']['atopile_address']
        if not a or a in by_address: raise ValueError('Duplicate or empty circuit address')
        by_address[a] = ref
    pages = []; covered = set()
    for page in spec['pages']:
        cfg = copy.deepcopy(page)
        if 'block_layout' in cfg:
            original = json.loads(read_source(ROOT / cfg['block_layout']))
            read_source(ROOT / original['pcb'])
            old_graph = board_graph(ROOT / original['pcb'])
            cfg['components'] = {}
            cfg['symbols'] = original['symbols']
            cfg['paper'] = original.get('paper', 'A4')
            for ref, c in old_graph.items():
                old = c['properties']['atopile_address']
                prefix = cfg['source_prefix']
                if not old.startswith(prefix + '.'): raise ValueError('Block address prefix changed')
                address = cfg['prefix'] + old[len(prefix):]
                cfg['components'][address] = original['components'][ref]
            for address, changes in cfg.get('component_overrides', {}).items():
                if address not in cfg['components']: raise ValueError('Unknown drawing override: ' + address)
                if set(changes) - {'at', 'text_offset', 'value'}: raise ValueError('Unsupported drawing override')
                cfg['components'][address].update(changes)
        else:
            cfg['symbols'] = spec['symbols']
        resolved = {}
        for address, component in cfg['components'].items():
            if address in covered: raise ValueError('Component is drawn more than once: ' + address)
            if address not in by_address: raise ValueError('Unknown component: ' + address)
            covered.add(address)
            resolved[by_address[address]] = component
        cfg['components'] = resolved
        subgraph = {ref: graph[ref] for ref in resolved}
        used = {c['symbol'] for c in resolved.values()}
        cfg['symbols'] = {k: v for k, v in cfg['symbols'].items() if k in used}
        cfg['net_names'] = spec['net_names']
        pages.append((cfg, subgraph))
    if covered != set(by_address): raise ValueError('Hierarchy does not cover every circuit component')
    return pages


def verify_export(graph, net_names, pages, xml_path):
    # Full physical pin/partition verification independent of the drawing generator.
    # Local KiCad labels are qualified with their page names; only the last name
    # is compared, with globally unique names enforced before drawing.
    import xml.etree.ElementTree as ET
    document = ET.parse(xml_path).getroot()
    components = document.find('components')
    if len(components) != len(graph) or {c.attrib['ref'] for c in components} != set(graph):
        raise ValueError('Exported component set differs')
    actual = {}; partitions = {}
    for net in document.find('nets'):
        pins = set()
        for pin in net.findall('node'):
            key = (pin.attrib['ref'], pin.attrib['pin'])
            if key in actual: raise ValueError('Duplicate exported pin')
            actual[key] = net.attrib['name'].rsplit('/', 1)[-1]
            pins.add(key)
        partitions[net.attrib['code']] = pins
    expected = {(ref, pin): net_names[name] for ref, c in graph.items() for pin, name in c['pads'].items()}
    expected_partition = {}
    for pin, net in expected.items(): expected_partition.setdefault(net, set()).add(pin)
    wanted = {frozenset(v) for v in expected_partition.values()}
    got = {frozenset(v) for v in partitions.values()}
    if got != wanted:
        raise ValueError(f'Exported net partition differs: {len(got - wanted)} extra / {len(wanted - got)} missing groups')
    for cfg, subgraph in pages:
        for ref, component in cfg['components'].items():
            for number in component.get('no_connect', []):
                pin = (ref, number)
                if len(expected_partition[expected[pin]]) != 1:
                    raise ValueError('NC is connected: ' + str(pin))
                expected[pin] = actual.get(pin)
    if actual != expected:
        wrong = {str(k): (expected.get(k), actual.get(k)) for k in expected.keys() | actual.keys() if expected.get(k) != actual.get(k)}
        raise ValueError('Exported net names differ: ' + json.dumps(wrong))
    return len(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    cli = native_cli()
    hashes = {}
    def read_source(path):
        path = path.resolve(); data = path.read_bytes()
        relative = str(path.relative_to(ROOT)); sha = hashlib.sha256(data).hexdigest()
        if relative in hashes and hashes[relative] != sha:
            raise ValueError('Source changed between reads: ' + relative)
        hashes[relative] = sha
        return data.decode()
    spec = json.loads(read_source(LAYOUT))
    pcb_path = ROOT / spec['pcb']
    read_source(pcb_path)
    for source in ['tools/generate_main_schematic.py', 'tools/main_schematic_page.py',
                   'tools/generate_schematics.py', 'tools/kicad_sexpr.py', 'hw/boards/blind-main/check_main.py']:
        read_source(ROOT / source)
    graph = board_graph(pcb_path)
    # The integration contract reads its eight independent reference captures.
    from check_main import BLOCKS
    for _, folder, target, _ in BLOCKS:
        read_source(ROOT / f'hw/layouts/{folder}/{target}/{target}.kicad_pcb')
    integrated = verify_integrated(graph)
    all_nets = {net for c in graph.values() for net in c['pads'].values()}
    if set(spec['net_names']) != all_nets or len(set(spec['net_names'].values())) != len(all_nets):
        raise ValueError('Names must cover exactly all distinct nets')
    pages = compile_pages(spec, graph, read_source)
    occurrences = {}
    for cfg, subgraph in pages:
        for net in {net for c in subgraph.values() for net in c['pads'].values()}:
            occurrences.setdefault(net, set()).add(cfg['id'])
    global_names = {spec['net_names'][net] for net, names in occurrences.items() if len(names) > 1}
    root_id = uid(PROJECT)
    root = n('kicad_sch', n('version', 20250114), n('generator', 'smart_blinds_schematic'),
             n('uuid', root_id), n('paper', 'A4'), n('title_block', n('title', 'Smart Blinds / integrated controller'),
             n('rev', 'STUDY'), n('comment', 1, 'Unrouted circuit; not for fabrication')), n('lib_symbols'))
    generated = {}; library = {}; page_records = []
    for i, (cfg, subgraph) in enumerate(pages):
        sheet_id = uid(PROJECT + '.sheet.' + cfg['id'])
        file_id = uid(PROJECT + '.file.' + cfg['id'])
        path = '/' + root_id + '/' + sheet_id
        drawing, lib = draw_page(cfg, subgraph, read_source, PROJECT, file_id, path, global_names)
        generated[cfg['id'] + '.kicad_sch'] = dumps(drawing) + '\n'
        for symbol in children(lib, 'symbol'):
            name = symbol[1]
            if name in library and library[name] != symbol: raise ValueError('Conflicting symbol definitions: ' + name)
            library[name] = symbol
        x = 20 + (i % 3) * 90; y = 45 + (i // 3) * 35
        root.append(n('sheet', n('at', x, y), n('size', 75, 22),
            n('stroke', n('width', 0.1524), n('type', Atom('default'))),
            n('fill', n('color', 0, 0, 0, 0)), n('uuid', sheet_id),
            n('property', 'Sheetname', cfg['short_title'], xy(x, y - 1.27), fx(1.27, n('justify', Atom('left'), Atom('bottom')))),
            n('property', 'Sheetfile', cfg['id'] + '.kicad_sch', xy(x, y + 23.27), fx(1, n('justify', Atom('left'), Atom('top')))),
            n('instances', n('project', PROJECT, n('path', '/' + root_id, n('page', str(i + 2)))))))
        root.append(n('text', f"{len(subgraph)} parts / {sum(len(c['pads']) for c in subgraph.values())} pin identities",
            xy(x + 4, y + 11), fx(1.27, n('justify', Atom('left'))),
            n('uuid', uid(PROJECT + '.summary.' + cfg['id']))))
        page_records.append({'file': cfg['id'] + '.kicad_sch', 'components': len(subgraph),
                             'pins': sum(len(c['pads']) for c in subgraph.values())})
    root.append(n('sheet_instances', n('path', '/', n('page', '1'))))
    for i, (text, y, size) in enumerate([
        ('SMART BLINDS / INTEGRATED CONTROLLER', 16, 2),
        (f'{len(graph)} circuit features. USB-C charging, protected pack input, radio, motor and local controls.', 26, 1.27),
        ('Sheet labels share only the explicitly named global nets. Open a sheet to inspect every part.', 34, 1.27),
        ('Captured circuit and native netlist are checked pin for pin. No routed or powered hardware acceptance.', 186, 1.1)]):
        root.append(n('text', text, xy(15, y), fx(size, n('justify', Atom('left'))), n('uuid', uid(PROJECT + '.note.' + str(i)))))
    generated[PROJECT + '.kicad_sch'] = dumps(root) + '\n'
    external = n('kicad_symbol_lib', n('version', 20241209), n('generator', 'smart_blinds_schematic'))
    for name, symbol in sorted(library.items()):
        symbol = copy.deepcopy(symbol); symbol[1] = name.split(':', 1)[1]; external.append(symbol)
    generated['SmartBlinds.kicad_sym'] = dumps(external) + '\n'
    generated['sym-lib-table'] = dumps(n('sym_lib_table', n('version', 7), n('lib', n('name', 'SmartBlinds'),
        n('type', 'KiCad'), n('uri', '${KIPRJMOD}/SmartBlinds.kicad_sym'), n('options', ''), n('descr', 'Reviewed controller symbols')))) + '\n'
    generated[PROJECT + '.kicad_pro'] = '{}\n'
    table = parse(read_source(pcb_path.parent / 'fp-lib-table')); dirs = {}
    used = {c['footprint'].split(':')[0] for c in graph.values()}
    for item in children(table, 'lib'):
        name = one(item, 'name')[1]
        if name in used: dirs[name] = Path(one(item, 'uri')[1].replace('${KIPRJMOD}', str(pcb_path.parent))).resolve()
    if set(dirs) != used: raise ValueError('Incomplete footprint libraries')
    for c in graph.values():
        lib, name = c['footprint'].split(':', 1)
        read_source(dirs[lib] / (name + '.kicad_mod'))
    def fp_table(base):
        return dumps(n('fp_lib_table', n('version', 7), *[n('lib', n('name', name), n('type', 'KiCad'),
            n('uri', '${KIPRJMOD}/' + os.path.relpath(directory, base)), n('options', ''), n('descr', 'Project footprint'))
            for name, directory in sorted(dirs.items())])) + '\n'
    generated['fp-lib-table'] = fp_table(OUTPUT)
    with tempfile.TemporaryDirectory(prefix='smart-blinds-main-sch-') as temp:
        tmp = Path(temp)
        for name, content in generated.items(): (tmp / name).write_text(content)
        (tmp / 'fp-lib-table').write_text(fp_table(tmp))
        schematic = tmp / (PROJECT + '.kicad_sch')
        def run(*command): subprocess.run([cli, *command], check=True, capture_output=True, text=True)
        run('sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(tmp / 'graph.xml'), str(schematic))
        pins = verify_export(graph, spec['net_names'], pages, tmp / 'graph.xml')
        run('sch', 'erc', '--format', 'json', '-o', str(tmp / 'erc.json'), str(schematic))
        report = json.loads((tmp / 'erc.json').read_text())
        findings = []; counts = {}
        for sheet in report['sheets']:
            for item in sheet.get('violations', []):
                counts[item['type']] = counts.get(item['type'], 0) + 1
                findings.append({'sheet': sheet['path'], 'type': item['type'],
                                 'items': sorted(v['description'] for v in item['items'])})
        findings.sort(key=lambda x: json.dumps(x, sort_keys=True))
        if findings != spec['expected_erc']:
            diagnostic = ROOT / 'work/main-schematic/erc-observed.json'
            diagnostic.parent.mkdir(parents=True, exist_ok=True)
            diagnostic.write_text(json.dumps(findings, indent=2) + '\n')
            raise ValueError(f'ERC findings differ: {counts}; inspect work/main-schematic/erc-observed.json')
        for relative, sha in hashes.items():
            if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != sha:
                raise ValueError('Input changed during generation: ' + relative)
        verification = {'status': 'integrated_graph_verified_unrouted_unpowered',
            'components': len(graph), 'pin_connections_checked': pins, 'child_sheets': len(pages),
            'pages': page_records, 'erc_clean': not findings, 'erc_counts': counts, 'erc_findings': findings,
            'integration_contract': integrated, 'source_sha256': dict(sorted(hashes.items()))}
        generated[PROJECT + '.verification.json'] = json.dumps(verification, indent=2) + '\n'
        for name, content in generated.items():
            path = OUTPUT / name
            if args.check:
                if not path.exists() or path.read_text() != content: raise ValueError('Stale generated file: ' + str(path))
            else: path.write_text(content)
        print(json.dumps({k: v for k, v in verification.items() if k != 'source_sha256'}, indent=2))


if __name__ == '__main__': main()
