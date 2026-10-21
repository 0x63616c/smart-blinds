"""Regressions for native-only execution and retaining real DRC failures."""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

import build_clean_main


class NativeBoundaryTests(unittest.TestCase):
    def test_host_is_rejected_before_output_or_native_import(self):
        with patch.object(build_clean_main.platform, 'system', return_value='Darwin'):
            with self.assertRaisesRegex(RuntimeError, 'host fallback is disabled'):
                build_clean_main.build(Path('/must-not-be-created'))

    def test_clearance_error_is_not_hidden_by_retained_hybrid_type(self):
        item = {'type': 'footprint_type_mismatch', 'severity': 'error', 'items': [{'uuid': 'hybrid'}]}
        boundary = {'retained_violations': [{'type': item['type'], 'severity': 'error', 'items': ['hybrid']}],
                    'remaining_connections': 2}
        report = {'violations': [item], 'unconnected_items': [{}, {}]}
        build_clean_main.check_drc(report, boundary)
        for field, value in [('type', 'clearance'), ('items', [{'uuid': 'unreviewed-part'}])]:
            changed = copy.deepcopy(report)
            changed['violations'][0][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                build_clean_main.check_drc(changed, boundary)
        report['unconnected_items'].append({})
        with self.assertRaisesRegex(RuntimeError, 'Unconnected-item count changed'):
            build_clean_main.check_drc(report, boundary)


if __name__ == '__main__':
    unittest.main()
