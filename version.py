"""A lightweight, dependency-free stand-in for `packaging.version` and
`packaging.specifiers`. Handles the common case -- dotted numeric
versions, optionally with a pre-release suffix (a1, b2, rc1) -- and
comma-separated specifier clauses like GitHub Security Advisories use
in `vulnerable_version_range` (e.g. ">= 2.0.0, < 2.6.0").

This intentionally does not implement the full PEP 440 grammar (local
version segments, epochs, post-releases, etc.) -- it covers what
real-world requirements.txt pins and GHSA ranges actually use, which is
the right scope for a project this size. See the README for the exact
boundary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_VERSION_RE = re.compile(
    r"^(?P<release>\d+(?:\.\d+)*)"
    r"(?:[-.]?(?P<pre_label>a|b|rc)(?P<pre_num>\d*))?$"
)

_PRE_ORDER = {"a": 0, "b": 1, "rc": 2, None: 3}  # None sorts after a/b/rc: final release


@dataclass(frozen=True, order=False, eq=False)
class Version:
    release: tuple[int, ...]
    pre_label: str | None
    pre_num: int

    def _padded_release(self, other: "Version") -> tuple[int, ...]:
        length = max(len(self.release), len(other.release))
        return self.release + (0,) * (length - len(self.release))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (
            self._padded_release(other) == other._padded_release(self)
            and self.pre_label == other.pre_label
            and self.pre_num == other.pre_num
        )

    def __hash__(self) -> int:
        # Hash on the un-padded fields is fine: equal Versions may pad
        # differently per-comparison, but hashing doesn't need padding
        # since we never rely on hash equality implying __eq__ here
        # (Version objects aren't used as dict/set keys in this project).
        return hash((self.release, self.pre_label, self.pre_num))

    def __lt__(self, other: "Version") -> bool:
        a, b = self._padded_release(other), other._padded_release(self)
        return (a, _PRE_ORDER[self.pre_label], self.pre_num) < (
            b,
            _PRE_ORDER[other.pre_label],
            other.pre_num,
        )

    def __le__(self, other: "Version") -> bool:
        return self == other or self < other

    def __gt__(self, other: "Version") -> bool:
        return other < self

    def __ge__(self, other: "Version") -> bool:
        return self == other or self > other

    def __str__(self) -> str:
        s = ".".join(str(p) for p in self.release)
        if self.pre_label is not None:
            s += f"{self.pre_label}{self.pre_num}"
        return s


class InvalidVersionError(ValueError):
    pass


def parse_version(text: str) -> Version:
    text = text.strip()
    match = _VERSION_RE.match(text)
    if not match:
        raise InvalidVersionError(f"cannot parse version string: {text!r}")

    release = tuple(int(p) for p in match.group("release").split("."))
    pre_label = match.group("pre_label")
    pre_num_raw = match.group("pre_num")
    pre_num = int(pre_num_raw) if pre_num_raw else 0
    return Version(release=release, pre_label=pre_label, pre_num=pre_num)


_OPERATORS = {
    "==": lambda v, target: v == target,
    "!=": lambda v, target: v != target,
    ">=": lambda v, target: v >= target,
    "<=": lambda v, target: v <= target,
    ">": lambda v, target: v > target,
    "<": lambda v, target: v < target,
}

_CLAUSE_RE = re.compile(r"^(==|!=|>=|<=|>|<)\s*(.+)$")


def version_satisfies(version_str: str, range_spec: str) -> bool:
    """Checks `version_str` against a comma-separated specifier string
    such as ">= 2.0.0, < 2.6.0" (all clauses must hold), or a single
    clause like "< 2.6.0". Raises InvalidVersionError on unparseable
    input rather than silently returning False, since a malformed range
    is a data problem the caller needs to know about, not a "no match".
    """
    version = parse_version(version_str)
    clauses = [c.strip() for c in range_spec.split(",") if c.strip()]
    if not clauses:
        raise InvalidVersionError(f"empty version range: {range_spec!r}")

    for clause in clauses:
        match = _CLAUSE_RE.match(clause)
        if not match:
            raise InvalidVersionError(f"cannot parse version clause: {clause!r}")
        op, target_str = match.group(1), match.group(2)
        target = parse_version(target_str)
        if not _OPERATORS[op](version, target):
            return False
    return True
