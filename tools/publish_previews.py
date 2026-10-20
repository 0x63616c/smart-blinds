#!/usr/bin/env python3
"""Adopt a CI preview artifact when its design inputs still match main."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MARKERS = re.compile(r'<!-- previews:start -->.*?<!-- previews:end -->', re.S)
# Match the render workflow's input paths. README prose outside the gallery may
# advance while rendering; a firmware-only change must not strand new images.
INPUTS = ['hw', 'cad', ':(glob)tools/*.py', 'docs/previews.json',
          '.github/workflows/design-previews.yml']


def gallery(text):
    if text.count('<!-- previews:start -->') != 1 or text.count('<!-- previews:end -->') != 1:
        raise ValueError('Expected exactly one preview marker pair')
    match = MARKERS.search(text)
    if not match:
        raise ValueError('Reversed preview markers')
    return match.group()


def adopt(root, artifact, source):
    if not re.fullmatch(r'[0-9a-f]{40}', source):
        raise ValueError('Expected full source commit SHA')
    generated = artifact / 'docs/generated'
    metadata = json.loads((generated / 'manifest.json').read_text())
    if metadata['source_commit'] != source or not metadata.get('source_snapshot_verified_unchanged'):
        raise ValueError('Artifact source or snapshot verification does not match')
    changed = subprocess.run(['git', 'diff', '--quiet', source, 'HEAD', '--', *INPUTS], cwd=root)
    if changed.returncode == 1:
        return False
    changed.check_returncode()
    for entry in metadata['designs']:
        for item in entry['outputs']:
            path = (generated / item['path']).resolve()
            if not path.is_relative_to(generated.resolve()) or not path.is_file():
                raise ValueError('Invalid artifact output path')
            if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('Artifact output hash mismatch')
    current = (root / 'README.md').read_text()
    gallery(current)
    replacement = gallery((artifact / 'README.md').read_text())
    updated = MARKERS.sub(lambda _: replacement, current)
    target = root / 'docs/generated'
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(generated, target)
    (root / 'README.md').write_text(updated)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-dir', required=True, type=Path)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    if adopt(ROOT, args.artifact_dir.resolve(), args.source_commit):
        print('Adopted verified previews; preserved current README prose.')
    else:
        print('Design inputs changed; leaving previews to the newer run.')
