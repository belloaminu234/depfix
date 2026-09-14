import unittest

from depfix.alerts import DependabotAlert
from depfix.registry import InMemoryRegistry, ReleaseInfo
from depfix.resolver import resolve


def make_alert(
    package_name="requests",
    vulnerable_version_range="< 2.31.0",
    first_patched_version="2.31.0",
    number=1,
) -> DependabotAlert:
    return DependabotAlert(
        number=number,
        state="open",
        ecosystem="pip",
        package_name=package_name,
        severity="high",
        ghsa_id="GHSA-test",
        summary="test advisory",
        vulnerable_version_range=vulnerable_version_range,
        first_patched_version=first_patched_version,
    )


class TestResolve(unittest.TestCase):
    def test_upgrades_to_first_patched_version_when_available(self):
        alert = make_alert()
        registry = InMemoryRegistry(
            {"requests": [ReleaseInfo(version="2.31.0", yanked=False)]}
        )
        result = resolve(alert, current_version="2.25.0", registry=registry)
        self.assertEqual(result.target_version, "2.31.0")
        self.assertIn("first_patched_version", result.reason)

    def test_no_op_when_current_version_not_vulnerable(self):
        alert = make_alert(vulnerable_version_range="< 2.31.0")
        registry = InMemoryRegistry({})
        result = resolve(alert, current_version="2.31.0", registry=registry)
        self.assertIsNone(result.target_version)
        self.assertIn("not affected", result.reason)

    def test_no_op_when_package_missing_from_requirements(self):
        alert = make_alert()
        registry = InMemoryRegistry({})
        result = resolve(alert, current_version=None, registry=registry)
        self.assertIsNone(result.target_version)
        self.assertIn("not found", result.reason)

    def test_falls_back_when_patched_version_is_yanked(self):
        alert = make_alert(first_patched_version="2.31.0")
        registry = InMemoryRegistry(
            {
                "requests": [
                    ReleaseInfo(version="2.31.0", yanked=True, yanked_reason="broken build"),
                    ReleaseInfo(version="2.32.0", yanked=False),
                ]
            }
        )
        result = resolve(alert, current_version="2.25.0", registry=registry)
        self.assertEqual(result.target_version, "2.32.0")
        self.assertIn("yanked", result.reason)

    def test_falls_back_when_patched_version_missing_from_registry(self):
        alert = make_alert(first_patched_version="2.31.0")
        registry = InMemoryRegistry(
            {"requests": [ReleaseInfo(version="2.32.0", yanked=False)]}
        )
        result = resolve(alert, current_version="2.25.0", registry=registry)
        self.assertEqual(result.target_version, "2.32.0")

    def test_falls_back_to_lowest_safe_release_not_highest(self):
        alert = make_alert(vulnerable_version_range="< 2.31.0", first_patched_version=None)
        registry = InMemoryRegistry(
            {
                "requests": [
                    ReleaseInfo(version="2.31.0", yanked=False),
                    ReleaseInfo(version="2.32.0", yanked=False),
                    ReleaseInfo(version="2.35.0", yanked=False),
                ]
            }
        )
        result = resolve(alert, current_version="2.25.0", registry=registry)
        self.assertEqual(result.target_version, "2.31.0")

    def test_no_resolution_when_no_safe_release_exists(self):
        alert = make_alert(first_patched_version="2.31.0")
        registry = InMemoryRegistry(
            {"requests": [ReleaseInfo(version="2.20.0", yanked=False)]}
        )
        result = resolve(alert, current_version="2.25.0", registry=registry)
        self.assertIsNone(result.target_version)
        self.assertIn("no safe", result.reason)

    def test_candidate_must_be_strictly_newer_than_current(self):
        # Even if some release satisfies "not vulnerable", it shouldn't
        # be offered as a "fix" if it's actually older than what's
        # already pinned (e.g. an old release outside the vulnerable
        # range for unrelated reasons).
        alert = make_alert(vulnerable_version_range=">= 3.0.0, < 3.1.0", first_patched_version=None)
        registry = InMemoryRegistry(
            {
                "requests": [
                    ReleaseInfo(version="2.31.0", yanked=False),
                    ReleaseInfo(version="3.2.0", yanked=False),
                ]
            }
        )
        result = resolve(alert, current_version="3.0.5", registry=registry)
        self.assertEqual(result.target_version, "3.2.0")


if __name__ == "__main__":
    unittest.main()
