import logging
import unittest
from unittest import mock

import types

from record.gum.observers.macos.app_and_browser_logging import MacOSAppAndBrowserInspector


class MacInspectorTests(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("test.macos.inspector")
        self.inspector = MacOSAppAndBrowserInspector(self.logger)
        self.inspector.last_frontmost_bundle_id = "company.thebrowser.browser"
        self.inspector.last_frontmost_pid = 123

    @mock.patch("record.gum.observers.macos.app_and_browser_logging._browser_url_via_accessibility")
    @mock.patch.object(MacOSAppAndBrowserInspector, "_run_browser_scripts")
    def test_accessibility_fallback_when_scripts_fail(self, run_scripts, fallback):
        run_scripts.return_value = None
        fallback.return_value = "https://arc.net"

        url = self.inspector.get_browser_url("Arc")

        self.assertEqual(url, "https://arc.net")
        fallback.assert_called_once_with(123)

    @mock.patch("record.gum.observers.macos.app_and_browser_logging._browser_url_via_accessibility")
    @mock.patch.object(MacOSAppAndBrowserInspector, "_run_browser_scripts")
    def test_cached_url_used_when_no_new_data(self, run_scripts, fallback):
        run_scripts.return_value = None
        fallback.return_value = None
        self.inspector.last_browser_urls["arc"] = "https://cached.example"

        url = self.inspector.get_browser_url("Arc")

        self.assertEqual(url, "https://cached.example")
        fallback.assert_called_once_with(123)

    @mock.patch("record.gum.observers.macos.app_and_browser_logging.subprocess.run")
    def test_run_browser_scripts_skips_nullish_responses(self, run_proc):
        run_proc.side_effect = [
            types.SimpleNamespace(returncode=0, stdout="missing value", stderr=""),
            types.SimpleNamespace(returncode=0, stdout="null", stderr=""),
            types.SimpleNamespace(returncode=0, stdout="https://arc.example", stderr=""),
        ]

        url = self.inspector._run_browser_scripts("Arc", "arc")

        self.assertEqual(url, "https://arc.example")
        self.assertEqual(run_proc.call_count, 3)


if __name__ == "__main__":
    unittest.main()
