#!/usr/bin/env python3
"""Compile the motor source against the saved PCB and bind the result to inputs."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'hw/boards/blind-controller'
PCB = ROOT / 'hw/layouts/blind-controller/motor-test/motor-test.kicad_pcb'


def inputs():
    paths = {BOARD / name for name in ('ato.yaml', 'motor-ratings.json', 'check_motor_ratings.py')}
    paths.add(Path(__file__).resolve())
    pending = [BOARD / 'motor.ato']
    while pending:
        path = pending.pop().resolve()
        if path in paths:
            continue
        paths.add(path)
        source = path.read_text()
        for imported in re.findall(r'from "([^"]+)" import', source):
            pending.append((path.parent / imported).resolve())
        for asset in re.findall(r'(?:footprint|symbol|model)="([^"]+)"', source):
            paths.add((path.parent / asset).resolve())
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ato', default=shutil.which('ato'))
    parser.add_argument('--record', action='store_true', help='Save local build evidence; CI always reruns the build')
    args = parser.parse_args()
    if not args.ato:
        parser.error('Install atopile 0.15.9 under Python 3.14, or pass --ato')
    version = subprocess.check_output([args.ato, '--version'], text=True).strip()
    if '0.15.9' not in version:
        parser.error(f'Expected atopile 0.15.9, got {version}')
    before = inputs()
    before_pcb = hashlib.sha256(PCB.read_bytes()).hexdigest()
    subprocess.run([args.ato, 'build', '-b', 'motor-test', '--frozen', '-v'], cwd=BOARD, check=True)
    subprocess.run([sys.executable, str(BOARD / 'check_motor_ratings.py')], cwd=BOARD, check=True)
    if inputs() != before or hashlib.sha256(PCB.read_bytes()).hexdigest() != before_pcb:
        raise RuntimeError('Inputs changed during the frozen build; repeat against stable sources')
    result = {
        'status': 'atopile_frozen_build_passed', 'atopile_version': '0.15.9',
        'command': 'python3 tools/verify_motor_build.py',
        'scope': 'Unplaced, unrouted motor subcircuit; whole-controller review and physical tests remain open.',
        'pcb_sha256': before_pcb, 'source_sha256': before,
    }
    if args.record:
        (BOARD / 'motor-build-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Frozen build and selected-part ratings passed; input snapshot unchanged.')


if __name__ == '__main__':
    main()
