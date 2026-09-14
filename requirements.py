"""Parses and rewrites requirements.txt files.

The design goal here is: a rewrite touches ONLY the version-pin lines
that actually changed, byte-for-byte identical everywhere else. That
means preserving comments, blank lines, extras (`package[extra]==1.0`),
environment markers (`; python_version >= "3.8"`), and line order exactly
as they appeared -- a diff of a requirements.txt update should show only
the lines that actually moved to a new version, nothing else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Matches "name[extras]==version ; marker" with name/extras/version
# captured, everything else (comparison operator, marker) left alone so
# we don't have to fully parse markers just to rewrite a version pin.
_PIN_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"(?P<extras>\[[^\]]*\])?"
    r"\s*(?P<op>==)\s*"
    r"(?P<version>[A-Za-z0-9.\-_]+)"
    r"(?P<rest>.*)$"
)


def normalize_name(name: str) -> str:
    """PEP 503 normalization: case- and separator-insensitive comparison,
    so "Flask-SQLAlchemy" and "flask_sqlalchemy" are recognized as the
    same package."""
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass
class RequirementLine:
    raw: str                    # the exact original line, including newline
    name: str | None = None     # normalized package name, or None for non-pin lines
    version: str | None = None  # pinned version, or None for non-pin lines


def parse_requirements(text: str) -> list[RequirementLine]:
    lines = []
    for raw_line in text.splitlines(keepends=True):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            # Blank lines, comments, and options like -r/-e/--index-url
            # are passed through untouched.
            lines.append(RequirementLine(raw=raw_line))
            continue

        match = _PIN_RE.match(stripped)
        if not match:
            # Anything we don't confidently recognize (a range like
            # ">=1.0,<2.0", a VCS URL, etc.) is left completely alone --
            # this tool only ever rewrites exact `==` pins.
            lines.append(RequirementLine(raw=raw_line))
            continue

        lines.append(
            RequirementLine(
                raw=raw_line,
                name=normalize_name(match.group("name")),
                version=match.group("version"),
            )
        )
    return lines


def render_requirements(lines: list[RequirementLine]) -> str:
    return "".join(line.raw for line in lines)


def bump_version(
    lines: list[RequirementLine], package_name: str, new_version: str
) -> tuple[list[RequirementLine], bool]:
    """Returns (new_lines, changed). Rewrites the `==` pin for
    `package_name` to `new_version`, preserving everything else on that
    line (extras, markers, trailing comment) exactly as it was.
    Non-matching lines are returned unchanged. If the package isn't
    found, `changed` is False and the input is returned as-is.
    """
    target = normalize_name(package_name)
    changed = False
    result = []

    for line in lines:
        if line.name != target:
            result.append(line)
            continue

        match = _PIN_RE.match(line.raw.strip())
        assert match is not None  # guaranteed by how `name` got set in parse_requirements

        new_stripped = (
            f"{match.group('name')}{match.group('extras') or ''}"
            f"=={new_version}{match.group('rest')}"
        )
        # Preserve the original line's trailing newline (or lack of one
        # on the final line of a file).
        newline = line.raw[len(line.raw.rstrip("\r\n")):]
        result.append(
            RequirementLine(raw=new_stripped + newline, name=target, version=new_version)
        )
        changed = True

    return result, changed
