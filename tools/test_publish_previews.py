import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from publish_previews import adopt


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


if __name__ == '__main__':
    unittest.main()
