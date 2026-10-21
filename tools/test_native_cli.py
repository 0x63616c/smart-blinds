"""Reject unsafe host fallback before running automated native schematic work."""
import unittest
from unittest.mock import patch

from generate_schematics import native_cli


class NativeCliTests(unittest.TestCase):
    def test_macos_is_denied_even_if_cli_is_installed(self):
        with patch('generate_schematics.platform.system', return_value='Darwin'), \
             patch('generate_schematics.shutil.which') as find:
            with self.assertRaisesRegex(RuntimeError, 'tools/kicad-run'):
                native_cli()
            find.assert_not_called()

    def test_missing_linux_cli_has_no_fallback(self):
        with patch('generate_schematics.platform.system', return_value='Linux'), \
             patch('generate_schematics.shutil.which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'no host fallback'):
                native_cli()

    def test_linux_cli_is_returned(self):
        with patch('generate_schematics.platform.system', return_value='Linux'), \
             patch('generate_schematics.shutil.which', return_value='/usr/bin/kicad-cli'):
            self.assertEqual(native_cli(), '/usr/bin/kicad-cli')


if __name__ == '__main__':
    unittest.main()
