import unittest

from depfix.alerts import parse_alert, parse_alerts

SAMPLE_ALERT = {
    "number": 1,
    "state": "open",
    "dependency": {
        "package": {"ecosystem": "pip", "name": "requests"},
        "manifest_path": "requirements.txt",
    },
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
}


class TestParseAlert(unittest.TestCase):
    def test_parses_all_fields(self):
        alert = parse_alert(SAMPLE_ALERT)
        self.assertEqual(alert.number, 1)
        self.assertEqual(alert.state, "open")
        self.assertEqual(alert.ecosystem, "pip")
        self.assertEqual(alert.package_name, "requests")
        self.assertEqual(alert.severity, "high")
        self.assertEqual(alert.ghsa_id, "GHSA-j8r2-6x86-q33q")
        self.assertEqual(alert.vulnerable_version_range, "< 2.31.0")
        self.assertEqual(alert.first_patched_version, "2.31.0")

    def test_missing_patched_version_is_none(self):
        raw = dict(SAMPLE_ALERT)
        raw["security_vulnerability"] = dict(SAMPLE_ALERT["security_vulnerability"])
        raw["security_vulnerability"]["first_patched_version"] = None
        alert = parse_alert(raw)
        self.assertIsNone(alert.first_patched_version)

    def test_parse_alerts_handles_a_list(self):
        alerts = parse_alerts([SAMPLE_ALERT, SAMPLE_ALERT])
        self.assertEqual(len(alerts), 2)


if __name__ == "__main__":
    unittest.main()
