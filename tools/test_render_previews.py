"""A mixed gallery must never invoke native KiCad on the macOS host."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import render_previews


class HostBoundaryTests(unittest.TestCase):
    def test_mixed_gallery_refuses_host_before_any_tool_launch(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest = Path(folder) / 'previews.json'
            manifest.write_text(json.dumps({'designs': [
                {'id': 'energy', 'kind': 'energy'},
                {'id': 'board', 'kind': 'pcb'},
            ]}))
            with patch.object(render_previews, 'MANIFEST', manifest), \
                 patch.object(render_previews.platform, 'system', return_value='Darwin'), \
                 patch.object(render_previews, 'run') as run, \
                 patch.object(render_previews, 'executable') as executable:
                with self.assertRaisesRegex(RuntimeError, 'host KiCad fallback is disabled'):
                    render_previews.render()
                run.assert_not_called()
                executable.assert_not_called()

    def test_source_generated_pcb_also_refuses_host(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest = Path(folder) / 'previews.json'
            manifest.write_text(json.dumps({'designs': [{'id': 'clean', 'kind': 'clean-pcb'}]}))
            with patch.object(render_previews, 'MANIFEST', manifest), \
                 patch.object(render_previews.platform, 'system', return_value='Darwin'), \
                 patch.object(render_previews, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'host KiCad fallback is disabled'):
                    render_previews.render()
                run.assert_not_called()

    def test_live_bound_capture_is_part_of_preview_publication_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            route = root / 'hw/routing/clean-main'
            route.mkdir(parents=True)
            (route / 'emit.py').write_text('# emitter')
            (root / 'capture.pcb').write_text('source')
            (route / 'source-binding.json').write_text(json.dumps({'files': {'capture.pcb': 'hash'}}))
            entry = {'kind': 'clean-pcb', 'source': 'hw/routing/clean-main/emit.py'}
            with patch.object(render_previews, 'ROOT', root):
                self.assertIn(root / 'capture.pcb', render_previews.entry_inputs(entry))
                (root / 'capture.pcb').unlink()
                with self.assertRaisesRegex(ValueError, 'Missing or non-project source'):
                    render_previews.entry_inputs(entry)


if __name__ == '__main__':
    unittest.main()
