import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from publish_previews import adopt, publish


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        self.root.mkdir()
        self.artifact = Path(self.temp.name) / 'artifact'
        self.generated = self.artifact / 'docs/generated'
        self.generated.mkdir(parents=True)
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        (self.root / 'cad').mkdir()
        (self.root / 'cad/design.scad').write_text('original source')
        (self.root / 'README.md').write_text('Original prose\n<!-- previews:start -->old<!-- previews:end -->\nOriginal tail')
        self.commit()
        self.source = self.git('rev-parse', 'HEAD').strip()
        self.artifact.joinpath('README.md').write_text('Stale prose\n<!-- previews:start -->fresh<!-- previews:end -->\nStale tail')
        data = b'fixture image bytes'
        self.generated.joinpath('image.png').write_bytes(data)
        self.metadata = {'source_commit': self.source, 'source_snapshot_verified_unchanged': True,
                         'designs': [{'outputs': [{'path': 'image.png', 'sha256': hashlib.sha256(data).hexdigest()}]}]}
        self.manifest()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')

    def manifest(self):
        self.generated.joinpath('manifest.json').write_text(json.dumps(self.metadata))

    def test_unrelated_commit_preserves_current_prose(self):
        readme = self.root / 'README.md'
        readme.write_text(readme.read_text().replace('Original', 'New'))
        (self.root / 'firmware').mkdir()
        (self.root / 'firmware/new.cpp').write_text('unrelated firmware')
        self.commit()
        self.assertTrue(adopt(self.root, self.artifact, self.source))
        self.assertEqual(readme.read_text(), 'New prose\n<!-- previews:start -->fresh<!-- previews:end -->\nNew tail')
        self.assertEqual((self.root / 'docs/generated/image.png').read_bytes(), b'fixture image bytes')

    def test_new_design_keeps_existing_publication(self):
        (self.root / 'cad/design.scad').write_text('new source')
        self.commit()
        before = (self.root / 'README.md').read_bytes()
        self.assertFalse(adopt(self.root, self.artifact, self.source))
        self.assertEqual((self.root / 'README.md').read_bytes(), before)
        self.assertFalse((self.root / 'docs/generated').exists())

    def test_wrong_source_rejects(self):
        with self.assertRaises(ValueError):
            adopt(self.root, self.artifact, '0' * 40)

    def test_tampered_output_rejects_before_mutation(self):
        self.generated.joinpath('image.png').write_bytes(b'changed')
        before = (self.root / 'README.md').read_bytes()
        with self.assertRaises(ValueError):
            adopt(self.root, self.artifact, self.source)
        self.assertEqual((self.root / 'README.md').read_bytes(), before)
        self.assertFalse((self.root / 'docs/generated').exists())

    def test_escaping_path_rejects(self):
        self.metadata['designs'][0]['outputs'][0]['path'] = '../outside.png'
        self.manifest()
        with self.assertRaises(ValueError):
            adopt(self.root, self.artifact, self.source)

    def test_duplicate_markers_reject_before_mutation(self):
        readme = self.root / 'README.md'
        readme.write_text(readme.read_text() + '<!-- previews:start -->extra<!-- previews:end -->')
        with self.assertRaises(ValueError):
            adopt(self.root, self.artifact, self.source)
        self.assertFalse((self.root / 'docs/generated').exists())

    def remote(self):
        remote = Path(self.temp.name) / 'remote.git'
        self.git('init', '--bare', '-q', str(remote))
        self.git('branch', '-M', 'main')
        self.git('remote', 'add', 'origin', str(remote))
        self.git('push', '-q', 'origin', 'main')
        return remote

    def racing_push(self, change):
        original = subprocess.run
        pushes = []

        def run(args, **kwargs):
            if args[:3] == ['git', 'push', 'origin']:
                pushes.append(1)
                if len(pushes) == 1:
                    change()
                    self.commit()
                    self.git('push', '-q', 'origin', 'main')
            return original(args, **kwargs)
        return run, pushes

    def test_remote_advance_revalidates_and_preserves_latest_prose(self):
        remote = self.remote()
        self.git('config', 'preview.fixture', 'repository-local-setting')
        def change():
            p = self.root / 'README.md'
            p.write_text(p.read_text().replace('Original', 'Latest'))
        run, pushes = self.racing_push(change)
        def configured_run(args, **kwargs):
            if args[:3] == ['git', 'push', 'origin']:
                value = subprocess.check_output(['git', 'config', 'preview.fixture'],
                                                cwd=kwargs['cwd'], text=True)
                self.assertEqual(value.strip(), 'repository-local-setting')
            return run(args, **kwargs)
        with patch('publish_previews.subprocess.run', side_effect=configured_run):
            self.assertEqual(publish(self.root, self.artifact, self.source), 'published')
        self.assertEqual(len(pushes), 2)
        readme = self.git('--git-dir', str(remote), 'show', 'main:README.md')
        self.assertEqual(readme, 'Latest prose\n<!-- previews:start -->fresh<!-- previews:end -->\nLatest tail')
        # The publisher never replaces the caller's checkout or its pending files.
        self.assertIn('>old<', (self.root / 'README.md').read_text())
        self.assertFalse((self.root / 'docs/generated').exists())
        self.assertEqual(self.git('worktree', 'list', '--porcelain').count('worktree '), 1)

    def test_remote_design_advance_discards_stale_preview(self):
        remote = self.remote()
        run, pushes = self.racing_push(lambda: (self.root / 'cad/design.scad').write_text('new design'))
        with patch('publish_previews.subprocess.run', side_effect=run):
            self.assertEqual(publish(self.root, self.artifact, self.source), 'superseded')
        self.assertEqual(len(pushes), 1)
        self.assertIn('>old<', self.git('--git-dir', str(remote), 'show', 'main:README.md'))

    def test_rejection_without_remote_advance_is_not_retried(self):
        self.remote()
        original = subprocess.run
        pushes = []
        def run(args, **kwargs):
            if args[:3] == ['git', 'push', 'origin']:
                pushes.append(1)
                return subprocess.CompletedProcess(args, 1, '', 'fixture rejection')
            return original(args, **kwargs)
        with patch('publish_previews.subprocess.run', side_effect=run):
            with self.assertRaises(subprocess.CalledProcessError):
                publish(self.root, self.artifact, self.source)
        self.assertEqual(len(pushes), 1)

    def test_repeated_advance_has_bounded_attempts(self):
        self.remote()
        original = subprocess.run
        pushes = []
        def run(args, **kwargs):
            if args[:3] == ['git', 'push', 'origin']:
                pushes.append(1)
                (self.root / 'unrelated.txt').write_text(str(len(pushes)))
                self.commit()
                self.git('push', '-q', 'origin', 'main')
            return original(args, **kwargs)
        with patch('publish_previews.subprocess.run', side_effect=run):
            with self.assertRaisesRegex(RuntimeError, 'bounded attempts'):
                publish(self.root, self.artifact, self.source)
        self.assertEqual(len(pushes), 3)

    def test_current_gallery_does_not_create_another_commit(self):
        remote = self.remote()
        self.assertEqual(publish(self.root, self.artifact, self.source), 'published')
        head = self.git('--git-dir', str(remote), 'rev-parse', 'main')
        self.assertEqual(publish(self.root, self.artifact, self.source), 'already_current')
        self.assertEqual(self.git('--git-dir', str(remote), 'rev-parse', 'main'), head)


if __name__ == '__main__':
    unittest.main()
