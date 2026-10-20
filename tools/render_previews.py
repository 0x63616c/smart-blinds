#!/usr/bin/env python3
"""Render registered CAD/KiCad sources without modifying electrical design files."""
from __future__ import annotations

import argparse
import hashlib
from html import escape
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'docs/previews.json'
OUTPUT = ROOT / 'docs/generated'


def run(args: list[str], *, env=None) -> str:
    result = subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}\n{result.stderr}")
    return (result.stdout + result.stderr).strip()


def executable(name: str, fallback: str | None = None) -> str:
    path = shutil.which(name)
    if not path and fallback and Path(fallback).is_file():
        path = fallback
    if not path:
        raise RuntimeError(f'{name} is required; see docs/previews.md')
    return path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_source(name: str) -> Path:
    path = (ROOT / name).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError(f'Missing or non-project source: {name}')
    return path


def entry_inputs(entry: dict) -> set[Path]:
    paths = {local_source(entry['source'])}
    for pattern in entry.get('dependencies', []):
        matches = [p for p in ROOT.glob(pattern) if p.is_file()]
        if not matches:
            raise ValueError(f'No dependencies match {pattern}')
        paths.update(matches)
    return paths


def model_files(board: Path, env: dict[str, str]) -> dict[str, str]:
    """KiCad can render with missing models; fail explicitly instead."""
    result = {}
    variables = dict(env, KIPRJMOD=str(board.parent))
    for raw in re.findall(r'\(model\s+"([^"\n]+)"', board.read_text()):
        def expand(match):
            key = match.group(1)
            if key not in variables:
                raise ValueError(f'Undefined 3D-model variable {key} in {board.name}')
            return variables[key]
        expanded = re.sub(r'\$\{([^}]+)\}', expand, raw)
        path = Path(expanded).expanduser()
        if not path.is_absolute():
            path = board.parent / path
        if not path.is_file():
            raise FileNotFoundError(f'Missing 3D model: {raw}')
        result[raw] = digest(path)
    return result


def render() -> None:
    manifest = json.loads(MANIFEST.read_text())
    entries = manifest['designs']
    if not entries:
        raise ValueError('No designs registered')
    ids = [entry['id'] for entry in entries]
    if len(set(ids)) != len(ids) or any(not re.fullmatch(r'[a-z0-9-]+', i) for i in ids):
        raise ValueError('Preview IDs must be unique lowercase names')
    env = os.environ.copy()
    if not env.get('KICAD10_3DMODEL_DIR'):
        for candidate in ('/Applications/KiCad.app/Contents/SharedSupport/3dmodels', '/usr/share/kicad/3dmodels'):
            if Path(candidate).is_dir():
                env['KICAD10_3DMODEL_DIR'] = candidate
                break
    versions = {}
    kicad = None
    if any(e['kind'] in ('pcb', 'schematic') for e in entries):
        kicad = executable('kicad-cli', '/Applications/KiCad.app/Contents/MacOS/kicad-cli')
        versions['kicad'] = run([kicad, 'version'])
        if not versions['kicad'].startswith('10.'):
            raise RuntimeError('This preview workflow requires KiCad 10')
    openscad = None
    if any(e['kind'] == 'openscad' for e in entries):
        openscad = executable('openscad')
        versions['openscad'] = run([openscad, '--version'])
    commit = run(['git', 'rev-parse', 'HEAD'])
    metadata = {'schema': 1, 'source_commit': commit, 'tools': versions,
                'manifest_sha256': digest(MANIFEST), 'renderer_sha256': digest(Path(__file__)),
                'validation': 'preview generation only; no physical validation', 'designs': []}
    source_paths = {MANIFEST, Path(__file__).resolve()}
    for entry in entries:
        source_paths.update(entry_inputs(entry))
    source_snapshot = {path: digest(path) for path in source_paths}
    gallery = []
    # Generate everything before replacing published outputs, so failures leave them intact.
    with tempfile.TemporaryDirectory(prefix='smart-blinds-previews-') as temp:
        destination = Path(temp)
        for entry in entries:
            source = local_source(entry['source'])
            input_paths = entry_inputs(entry)
            inputs = {str(p.relative_to(ROOT)): digest(p) for p in sorted(input_paths)}
            status = run(['git', 'status', '--porcelain', '--', *inputs])
            item = {'id': entry['id'], 'source': entry['source'], 'inputs_sha256': inputs,
                    'source_files_dirty': bool(status), 'role': entry['role'], 'outputs': []}
            folder = destination / entry['id']
            folder.mkdir()
            print(f"Rendering {entry['title']}", flush=True)
            if entry['kind'] == 'pcb':
                item['models_sha256'] = model_files(source, env)
                image = folder / 'assembly.png'
                size=entry.get('image_size',[1600,1000]);rotate=entry.get('rotate',[335,0,15]);zoom=entry.get('zoom',1)
                if len(size)!=2 or any(type(v)!=int or not 256<=v<=4096 for v in size):
                    raise ValueError('PCB image size requires two bounded integer dimensions')
                if len(rotate)!=3 or any(type(v) not in (int,float) or not -360<=v<=360 for v in rotate):
                    raise ValueError('PCB rotation requires three finite angles')
                if type(zoom) not in (int,float) or not .1<=zoom<=3:
                    raise ValueError('PCB zoom must be within 0.1–3')
                run([kicad, 'pcb', 'render', '--output', str(image), '--width', str(size[0]),
                     '--height', str(size[1]), '--quality', 'high', '--background', 'transparent',
                     '--rotate', ','.join(map(str,rotate)), '--zoom', str(zoom), str(source)], env=env)
                layout = folder / 'top.svg'
                run([kicad, 'pcb', 'export', 'svg', '--output', str(layout), '--mode-single',
                     '--layers', 'F.Cu,F.SilkS,Edge.Cuts', '--page-size-mode', '2',
                     '--exclude-drawing-sheet', str(source)], env=env)
            elif entry['kind'] == 'schematic':
                run([kicad, 'sch', 'export', 'svg', '--output', str(folder), str(source)], env=env)
                pages = sorted(folder.glob('*.svg'))
                if not pages:
                    raise RuntimeError('No schematic pages produced')
                image = pages[0]
            elif entry['kind'] in ('footprints', 'holder-footprints'):
                # The CAD study owns the comparison dimensions and SVG generator.
                holder_study = entry['kind'] == 'holder-footprints'
                spec = importlib.util.spec_from_file_location('cad_study', ROOT / ('cad/build_v2.py' if holder_study else 'cad/build.py'))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                image = folder / 'footprints.svg'
                (module.svg if holder_study else module.write_footprints)(json.loads(source.read_text()), image)
            elif entry['kind'] == 'openscad':
                image = folder / 'assembly.png'
                mode = entry.get('render_mode', 'preview')
                if mode not in ('preview', 'render'):
                    raise ValueError('OpenSCAD render_mode must be preview or render')
                command = [openscad, '--' + mode, '--imgsize=1600,1000', '--viewall', '--autocenter',
                           '--projection=o', '--colorscheme=Tomorrow', '-o', str(image)]
                if 'camera' in entry:
                    camera = entry['camera']
                    if not isinstance(camera, list) or len(camera) != 7 or any(
                            type(v) not in (int, float) or not (-1e6 < v < 1e6) for v in camera
                    ) or camera[-1] <= 0:
                        raise ValueError('OpenSCAD camera needs seven finite numbers and positive distance')
                    command.append('--camera=' + ','.join(str(v) for v in camera))
                for key, value in entry.get('defines', {}).items():
                    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', key):
                        raise ValueError('Invalid OpenSCAD variable')
                    command.extend(['-D', f'{key}={json.dumps(value)}'])
                run([*command, str(source)], env=env)
            else:
                raise ValueError(f"Unknown preview kind: {entry['kind']}")
            # KiCad emits trailing XML whitespace; normalize it for readable diffs.
            for svg in folder.glob('*.svg'):
                svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
            for path in sorted(folder.rglob('*')):
                if path.is_file():
                    if path.stat().st_size == 0:
                        raise RuntimeError(f'Empty render: {path.name}')
                    item['outputs'].append({'path': str(path.relative_to(destination)), 'sha256': digest(path)})
            metadata['designs'].append(item)
            image_link = f'docs/generated/{image.relative_to(destination)}'
            if entry.get('collapsed', False):
                gallery.extend(['<details>', f"<summary>{escape(entry['title'])}</summary>", ''])
            else:
                gallery.extend([f"### {entry['title']}", ''])
            gallery.extend([entry['role'], '',
                            f"![{entry['title']}]({image_link})", '',
                            f"[Source]({entry['source']}) · [Generated files](docs/generated/{entry['id']}/)", ''])
            if entry.get('collapsed', False):
                gallery.extend(['</details>', ''])
        final_paths = {MANIFEST, Path(__file__).resolve()}
        for entry in entries:
            final_paths.update(entry_inputs(entry))
        if final_paths != source_paths or any(digest(path) != value for path, value in source_snapshot.items()):
            raise RuntimeError('Design sources changed during rendering; previous published previews preserved. Rerun from stable sources.')
        for entry, item in zip(entries, metadata['designs']):
            if entry['kind'] == 'pcb' and model_files(local_source(entry['source']), env) != item['models_sha256']:
                raise RuntimeError('PCB models changed during rendering; previous published previews preserved.')
        metadata['source_snapshot_verified_unchanged'] = True
        (destination / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
        readme = (ROOT / 'README.md').read_text()
        replacement = '<!-- previews:start -->\n' + '\n'.join(gallery) + '\n<!-- previews:end -->'
        updated, count = re.subn(r'<!-- previews:start -->.*?<!-- previews:end -->', lambda _: replacement, readme, flags=re.S)
        if count != 1:
            raise ValueError('README must contain exactly one preview marker pair')
        if OUTPUT.exists():
            shutil.rmtree(OUTPUT)
        shutil.copytree(destination, OUTPUT)
        (ROOT / 'README.md').write_text(updated)
    print(f'Updated {len(entries)} previews; source commit {commit[:12]}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    render()
