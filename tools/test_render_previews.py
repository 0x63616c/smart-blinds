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


if __name__ == '__main__':
    unittest.main()
