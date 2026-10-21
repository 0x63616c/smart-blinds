#!/usr/bin/env python3
"""Build and check the current partial route in a new output directory.

Run the normal/frozen circuit builds first. Native execution is Linux-only;
on macOS use tools/kicad-run. Never writes the canonical circuit capture.
"""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / 'hw/routing/clean-main'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_drc(report, boundary):
    """Keep the unfinished route and named hybrid errors visible and bounded."""
    actual = []
    for finding in report['violations']:
        actual.append({
            'type': finding['type'],
            'severity': finding['severity'],
            'items': sorted(item['uuid'] for item in finding['items']),
        })
    key = lambda value: json.dumps(value, sort_keys=True)
    if sorted(actual, key=key) != sorted(boundary['retained_violations'], key=key):
        raise RuntimeError('Native DRC differs from the named retained findings; inspect drc.json')
    if len(report['unconnected_items']) != boundary['remaining_connections']:
        raise RuntimeError('Unconnected-item count changed; review the actual circuit before updating the boundary')
    if report.get('schematic_parity'):
        raise RuntimeError('Unexpected schematic parity findings')
    return dict(collections.Counter(item['type'] for item in report['violations']))


def build(output, *, faults=False):
    if platform.system() != 'Linux':
        raise RuntimeError('Native clean-main build requires isolated Linux tools/kicad-run or Linux CI; host fallback is disabled')
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError('Use a new output directory; preserve the previous native result')
    sys.path.insert(0, str(ROUTE))
    import emit
    import check
    import geometry

    binding, source_root = emit.inputs(ROOT)
    guards = {source_root / name: value for name, value in binding['files'].items()}
    emit.write(output, ROOT)
    board_path = output / 'candidate.kicad_pcb'
    project_path = output / 'candidate.kicad_pro'
    project_bytes = project_path.read_bytes()
    before = board_path.read_bytes()
    (output / 'unfilled.kicad_pcb').write_bytes(before)
    check.verify(geometry.parse(before.decode()), board_path, source_root=ROOT)
    # wx must exist before importing/using pcbnew. This path is deliberately
    # unreachable on the macOS host, even when a host KiCad is installed.
    import wx
    app = wx.App(False)
    import pcbnew

    version = pcbnew.GetBuildVersion()
    if not version.startswith('10.'):
        raise RuntimeError('The reviewed native workflow requires KiCad 10')
    library = []
    for path in sorted((output / 'clean-main.pretty').glob('*.kicad_mod')):
        footprint = pcbnew.FootprintLoad(str(path.parent), path.stem)
        if not footprint:
            raise RuntimeError(f'Native library load failed: {path.name}')
        library.append({'name': path.stem, 'pads': len(list(footprint.Pads()))})
    (output / 'library-load.json').write_text(json.dumps(library, indent=2) + '\n')
    board = pcbnew.LoadBoard(str(board_path))
    if not board:
        raise RuntimeError('Native board load failed')
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(board_path), board)
    # The reviewed rules remain authority after native serialization. KiCad
    # may materialize project defaults while saving a new board.
    serialized_project = digest(project_path)
    project_path.write_bytes(project_bytes)
    if not pcbnew.LoadBoard(str(board_path)):
        raise RuntimeError('Saved board could not be reloaded')
    result = subprocess.run([
        'kicad-cli', 'pcb', 'drc', '--severity-all', '--format', 'json',
        '-o', str(output / 'drc.json'), str(board_path),
    ], text=True, capture_output=True)
    (output / 'drc.log').write_text(result.stdout + result.stderr)
    if result.returncode not in (0, 5):
        raise RuntimeError(f'Native DRC failed ({result.returncode}); inspect drc.log')
    drc = json.loads((output / 'drc.json').read_text())
    boundary = json.loads((ROUTE / 'native-boundary.json').read_text())
    counts = check_drc(drc, boundary)
    verified = check.verify(geometry.parse(board_path.read_text()), board_path, filled=True, source_root=ROOT)
    (output / 'physical-check.json').write_text(json.dumps(verified, indent=2) + '\n')
    if faults:
        subprocess.run([sys.executable, str(ROUTE / 'test_faults.py'), str(board_path),
                        '--source-root', str(ROOT), '--output', str(output / 'faults.json')], check=True)
    for path, expected in guards.items():
        if digest(path) != expected:
            raise RuntimeError(f'Canonical source changed during native build: {path.relative_to(ROOT)}')
    receipt = {
        'status': 'Checked partial route; not a fabrication release',
        'kicad_version': version,
        'source_sha256': binding['files'][binding['source']],
        'board_sha256': digest(board_path),
        'project_sha256': digest(output / 'candidate.kicad_pro'),
        'project_sha256_after_native_save': serialized_project,
        'drc_sha256': digest(output / 'drc.json'),
        'retained_violations': counts,
        'remaining_connections': len(drc['unconnected_items']),
        'library_variants': len(library),
        'source_inputs_unchanged': True,
        'physical_checks': 'passed on saved filled board',
        'fault_checks': 'passed' if faults else 'not run',
    }
    (output / 'native.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--faults', action='store_true')
    args = parser.parse_args()
    print(json.dumps(build(args.output, faults=args.faults), indent=2))
