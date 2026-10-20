#!/usr/bin/env python3
"""Adopt a CI preview artifact when its design inputs still match main."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

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


def publish(root, artifact, source, attempts=3):
    """Retry only remote-advance races, always in a disposable checkout.

    Never rebase a generated commit: revalidate source inputs and preserve the
    latest README on each attempt. The caller's checkout is never reset.
    """
    with tempfile.TemporaryDirectory(prefix='preview-publication-') as directory:
        checkout = Path(directory) / 'checkout'
        # A worktree shares checkout@v4's repository-local authentication.
        # A fresh clone/init would silently lose its configured HTTP header.
        subprocess.run(['git', 'worktree', 'add', '--detach', str(checkout), 'HEAD'],
                       cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            return publish_checkout(checkout, artifact, source, attempts)
        finally:
            subprocess.run(['git', 'worktree', 'remove', '--force', str(checkout)],
                           cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def publish_checkout(checkout, artifact, source, attempts):
    def git(*args, check=True):
        return subprocess.run(['git', *args], cwd=checkout, check=check,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    previous_base = None
    failed_push = None
    for _ in range(attempts):
        git('fetch', '--no-tags', 'origin', 'main')
        base = git('rev-parse', 'FETCH_HEAD').stdout.strip()
        if base == previous_base:
            # Authentication/network/repository rejection is not a race.
            failed_push.check_returncode()
        git('checkout', '--detach', '--force', base)
        if not adopt(checkout, artifact, source):
            return 'superseded'
        git('add', '--', 'README.md', 'docs/generated')
        changed = git('diff', '--cached', '--quiet', check=False)
        if changed.returncode == 0:
            return 'already_current'
        if changed.returncode != 1:
            changed.check_returncode()
        git('-c', 'user.name=github-actions[bot]',
            '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
            'commit', '-qm', 'docs: refresh generated design previews')
        failed_push = git('push', 'origin', 'HEAD:main', check=False)
        if failed_push.returncode == 0:
            return 'published'
        previous_base = base
    raise RuntimeError('Preview publication did not succeed within the bounded attempts')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-dir', required=True, type=Path)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--publish', action='store_true', help='Publish from a disposable checkout with bounded race retries')
    args = parser.parse_args()
    if args.publish:
        print('Preview publication:', publish(ROOT, args.artifact_dir.resolve(), args.source_commit))
    elif adopt(ROOT, args.artifact_dir.resolve(), args.source_commit):
        print('Adopted verified previews; preserved current README prose.')
    else:
        print('Design inputs changed; leaving previews to the newer run.')
