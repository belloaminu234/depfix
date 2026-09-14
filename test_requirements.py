import unittest

from depfix.requirements import (
    bump_version,
    normalize_name,
    parse_requirements,
    render_requirements,
)


class TestNormalizeName(unittest.TestCase):
    def test_case_and_separator_insensitive(self):
        self.assertEqual(normalize_name("Flask-SQLAlchemy"), normalize_name("flask_sqlalchemy"))
        self.assertEqual(normalize_name("flask.sqlalchemy"), "flask-sqlalchemy")


class TestParseRequirements(unittest.TestCase):
    def test_simple_pin(self):
        lines = parse_requirements("requests==2.28.0\n")
        self.assertEqual(lines[0].name, "requests")
        self.assertEqual(lines[0].version, "2.28.0")

    def test_comments_and_blank_lines_pass_through(self):
        text = "# top comment\n\nrequests==2.28.0\n"
        lines = parse_requirements(text)
        self.assertIsNone(lines[0].name)
        self.assertIsNone(lines[1].name)
        self.assertEqual(lines[2].name, "requests")

    def test_option_lines_pass_through(self):
        text = "-r base.txt\n--index-url https://example.com\nrequests==2.28.0\n"
        lines = parse_requirements(text)
        self.assertIsNone(lines[0].name)
        self.assertIsNone(lines[1].name)
        self.assertEqual(lines[2].name, "requests")

    def test_extras_and_markers_preserved_as_non_version_fields(self):
        lines = parse_requirements('requests[security]==2.28.0 ; python_version >= "3.8"\n')
        self.assertEqual(lines[0].name, "requests")
        self.assertEqual(lines[0].version, "2.28.0")

    def test_non_pin_specifier_left_untouched(self):
        # A range specifier (not an exact `==` pin) is out of scope for
        # this tool -- it should be passed through, not misparsed.
        lines = parse_requirements("requests>=2.0,<3.0\n")
        self.assertIsNone(lines[0].name)

    def test_roundtrip_preserves_exact_text(self):
        text = "# comment\nrequests==2.28.0\n\nflask==2.0.0  # pinned for compat\n"
        lines = parse_requirements(text)
        self.assertEqual(render_requirements(lines), text)


class TestBumpVersion(unittest.TestCase):
    def test_bumps_matching_package_only(self):
        text = "requests==2.28.0\nflask==2.0.0\n"
        lines = parse_requirements(text)
        new_lines, changed = bump_version(lines, "requests", "2.31.0")
        self.assertTrue(changed)
        self.assertEqual(render_requirements(new_lines), "requests==2.31.0\nflask==2.0.0\n")

    def test_preserves_extras_and_markers_on_bump(self):
        text = 'requests[security]==2.28.0 ; python_version >= "3.8"\n'
        lines = parse_requirements(text)
        new_lines, changed = bump_version(lines, "requests", "2.31.0")
        self.assertTrue(changed)
        self.assertEqual(
            render_requirements(new_lines),
            'requests[security]==2.31.0 ; python_version >= "3.8"\n',
        )

    def test_name_matching_is_normalized(self):
        text = "Flask-SQLAlchemy==2.5.1\n"
        lines = parse_requirements(text)
        new_lines, changed = bump_version(lines, "flask_sqlalchemy", "3.0.0")
        self.assertTrue(changed)
        self.assertIn("==3.0.0", render_requirements(new_lines))

    def test_bumping_missing_package_is_a_no_op(self):
        text = "requests==2.28.0\n"
        lines = parse_requirements(text)
        new_lines, changed = bump_version(lines, "flask", "3.0.0")
        self.assertFalse(changed)
        self.assertEqual(render_requirements(new_lines), text)

    def test_other_lines_are_byte_for_byte_unchanged(self):
        text = "# keep this comment\nrequests==2.28.0\nflask==2.0.0  # trailing note\n"
        lines = parse_requirements(text)
        new_lines, _ = bump_version(lines, "requests", "2.31.0")
        result = render_requirements(new_lines)
        self.assertIn("# keep this comment\n", result)
        self.assertIn("flask==2.0.0  # trailing note\n", result)

    def test_final_line_without_trailing_newline_preserved(self):
        text = "requests==2.28.0"  # no trailing newline
        lines = parse_requirements(text)
        new_lines, changed = bump_version(lines, "requests", "2.31.0")
        self.assertTrue(changed)
        self.assertEqual(render_requirements(new_lines), "requests==2.31.0")


if __name__ == "__main__":
    unittest.main()
