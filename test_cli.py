"""Tests the actual `depfix.cli.main()` entry point -- argument parsing,
file I/O, exit codes, and error handling -- with PyPIRegistry patched out
so no real network call is made.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from depfix import cli
from depfix.registry import InMemoryRegistry, ReleaseInfo

ALERTS_FIXTURE = [
    {
        "number": 1,
        "state": "open",
        "dependency": {"package": {"ecosystem": "pip", "name": "requests"}},
        "security_advisory": {
            "ghsa_id": "GHSA-j8r2-6x86-q33q",
            "summary": "test advisory",
            "severity": "high",
        },
        "security_vulnerability": {
            "package": {"ecosystem": "pip", "name": "requests"},
            "severity": "high",
            "vulnerable_version_range": "< 2.31.0",
            "first_patched_version": {"identifier": "2.31.0"},
        },
    }
]


class TestCliMain(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.req_path = Path(self.tmp.name) / "requirements.txt"
        self.alerts_path = Path(self.tmp.name) / "alerts.json"
        self.req_path.write_text("requests==2.25.0\n")
        self.alerts_path.write_text(json.dumps(ALERTS_FIXTURE))

        fake_registry = InMemoryRegistry(
            {"requests": [ReleaseInfo(version="2.31.0", yanked=False)]}
        )
        patcher = patch.object(cli, "PyPIRegistry", return_value=fake_registry)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_writes_fix_by_default(self):
        exit_code = cli.main(
            ["--requirements", str(self.req_path), "--alerts", str(self.alerts_path)]
        )
        self.assertEqual(exit_code, 0)
        self.assertIn("requests==2.31.0", self.req_path.read_text())

    def test_dry_run_does_not_write_file(self):
        original = self.req_path.read_text()
        exit_code = cli.main(
            [
                "--requirements", str(self.req_path),
                "--alerts", str(self.alerts_path),
                "--dry-run",
            ]
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(self.req_path.read_text(), original)

    def test_missing_requirements_file_returns_nonzero(self):
        exit_code = cli.main(
            ["--requirements", "/nonexistent/requirements.txt", "--alerts", str(self.alerts_path)]
        )
        self.assertNotEqual(exit_code, 0)

    def test_malformed_alerts_json_returns_nonzero(self):
        self.alerts_path.write_text("{not valid json")
        exit_code = cli.main(
            ["--requirements", str(self.req_path), "--alerts", str(self.alerts_path)]
        )
        self.assertNotEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
