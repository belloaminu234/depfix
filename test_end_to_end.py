"""End-to-end tests: writes real requirements.txt and alerts.json files
to a temp directory and runs the actual CLI entry point against them,
using an InMemoryRegistry in place of live PyPI so the test suite has no
network dependency. This exercises the full pipeline: file I/O, JSON
parsing, resolution, and rewriting.
"""

import json
import tempfile
import unittest
from pathlib import Path

from depfix.alerts import parse_alerts
from depfix.registry import InMemoryRegistry, ReleaseInfo
from depfix.updater import apply_alerts

ALERTS_FIXTURE = [
    {
        "number": 1,
        "state": "open",
        "dependency": {"package": {"ecosystem": "pip", "name": "requests"}},
        "security_advisory": {
            "ghsa_id": "GHSA-j8r2-6x86-q33q",
            "summary": "Requests vulnerable to session fixation",
            "severity": "high",
        },
        "security_vulnerability": {
            "package": {"ecosystem": "pip", "name": "requests"},
            "severity": "high",
            "vulnerable_version_range": "< 2.31.0",
            "first_patched_version": {"identifier": "2.31.0"},
        },
    },
    {
        # This one shouldn't touch anything: flask is already >= the
        # patched version, so it's not currently vulnerable.
        "number": 2,
        "state": "open",
        "dependency": {"package": {"ecosystem": "pip", "name": "flask"}},
        "security_advisory": {
            "ghsa_id": "GHSA-fake-flask",
            "summary": "hypothetical flask advisory",
            "severity": "moderate",
        },
        "security_vulnerability": {
            "package": {"ecosystem": "pip", "name": "flask"},
            "severity": "moderate",
            "vulnerable_version_range": "< 2.0.0",
            "first_patched_version": {"identifier": "2.0.0"},
        },
    },
    {
        # A non-pip ecosystem alert should be reported as skipped, not
        # crash the tool.
        "number": 3,
        "state": "open",
        "dependency": {"package": {"ecosystem": "npm", "name": "lodash"}},
        "security_advisory": {
            "ghsa_id": "GHSA-fake-lodash",
            "summary": "hypothetical lodash advisory",
            "severity": "high",
        },
        "security_vulnerability": {
            "package": {"ecosystem": "npm", "name": "lodash"},
            "severity": "high",
            "vulnerable_version_range": "< 4.17.21",
            "first_patched_version": {"identifier": "4.17.21"},
        },
    },
]

REQUIREMENTS_FIXTURE = (
    "# core dependencies\n"
    "requests==2.25.0\n"
    "flask==2.0.0  # already patched\n"
    "\n"
    "# dev dependencies\n"
    "pytest==7.0.0\n"
)


class TestEndToEndUpdate(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryRegistry(
            {"requests": [ReleaseInfo(version="2.31.0", yanked=False)]}
        )
        self.alerts = parse_alerts(ALERTS_FIXTURE)

    def test_full_pipeline_fixes_only_the_vulnerable_package(self):
        result = apply_alerts(REQUIREMENTS_FIXTURE, self.alerts, self.registry)

        self.assertTrue(result.changed)
        self.assertIn("requests==2.31.0", result.updated_text)
        # flask and pytest, and all comments/blank lines, are untouched.
        self.assertIn("flask==2.0.0  # already patched", result.updated_text)
        self.assertIn("pytest==7.0.0", result.updated_text)
        self.assertIn("# core dependencies", result.updated_text)

        by_package = {r.package_name: r for r in result.resolutions}
        self.assertEqual(by_package["requests"].target_version, "2.31.0")
        self.assertIsNone(by_package["flask"].target_version)
        self.assertIn("not affected", by_package["flask"].reason)
        self.assertIsNone(by_package["lodash"].target_version)
        self.assertIn("unsupported ecosystem", by_package["lodash"].reason)

    def test_writes_updated_file_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            req_path = Path(tmp) / "requirements.txt"
            req_path.write_text(REQUIREMENTS_FIXTURE)

            result = apply_alerts(req_path.read_text(), self.alerts, self.registry)
            req_path.write_text(result.updated_text)

            on_disk = req_path.read_text()
            self.assertIn("requests==2.31.0", on_disk)
            self.assertIn("flask==2.0.0  # already patched", on_disk)

    def test_no_changes_when_nothing_is_vulnerable(self):
        registry = InMemoryRegistry({})
        already_safe = "requests==2.31.0\nflask==2.0.0\n"
        result = apply_alerts(already_safe, self.alerts, registry)
        self.assertFalse(result.changed)
        self.assertEqual(result.updated_text, already_safe)

    def test_closed_alert_is_skipped(self):
        raw = json.loads(json.dumps(ALERTS_FIXTURE))  # deep copy
        raw[0]["state"] = "dismissed"
        alerts = parse_alerts(raw)
        result = apply_alerts(REQUIREMENTS_FIXTURE, alerts, self.registry)

        requests_resolution = next(r for r in result.resolutions if r.package_name == "requests")
        self.assertIsNone(requests_resolution.target_version)
        self.assertIn("not 'open'", requests_resolution.reason)


if __name__ == "__main__":
    unittest.main()
