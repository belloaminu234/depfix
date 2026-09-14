import unittest

from depfix.version import InvalidVersionError, parse_version, version_satisfies


class TestVersionParsing(unittest.TestCase):
    def test_simple_dotted_version(self):
        v = parse_version("2.31.0")
        self.assertEqual(v.release, (2, 31, 0))

    def test_short_version_compares_equal_to_padded_version(self):
        self.assertEqual(parse_version("2.1"), parse_version("2.1.0"))

    def test_prerelease_sorts_before_final(self):
        self.assertLess(parse_version("2.0a1"), parse_version("2.0"))
        self.assertLess(parse_version("2.0rc1"), parse_version("2.0"))

    def test_prerelease_ordering_alpha_beta_rc(self):
        self.assertLess(parse_version("2.0a1"), parse_version("2.0b1"))
        self.assertLess(parse_version("2.0b1"), parse_version("2.0rc1"))

    def test_invalid_version_raises(self):
        with self.assertRaises(InvalidVersionError):
            parse_version("not-a-version")


class TestVersionSatisfies(unittest.TestCase):
    def test_single_less_than_clause(self):
        self.assertTrue(version_satisfies("2.5.0", "< 2.6.0"))
        self.assertFalse(version_satisfies("2.6.0", "< 2.6.0"))

    def test_range_with_two_clauses(self):
        self.assertTrue(version_satisfies("2.3.0", ">= 2.0.0, < 2.6.0"))
        self.assertFalse(version_satisfies("1.9.0", ">= 2.0.0, < 2.6.0"))
        self.assertFalse(version_satisfies("2.6.0", ">= 2.0.0, < 2.6.0"))

    def test_exact_match_clause(self):
        self.assertTrue(version_satisfies("1.2.3", "== 1.2.3"))
        self.assertFalse(version_satisfies("1.2.4", "== 1.2.3"))

    def test_malformed_range_raises(self):
        with self.assertRaises(InvalidVersionError):
            version_satisfies("1.0.0", "not a real range")


if __name__ == "__main__":
    unittest.main()
