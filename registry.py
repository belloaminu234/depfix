"""Looks up package release information -- this is the "check package
docs" step: before pinning a version, we confirm it actually exists on
the registry and hasn't been yanked (pulled by the maintainers, usually
because it turned out to be broken or itself insecure).

`PackageRegistry` is a Protocol so the resolver can be tested against an
in-memory fake with no network access, while still having a real
implementation for actual use. This is the same reason production code
puts a repository/gateway interface between business logic and any
external system: the logic that decides *which* version to pick
shouldn't need a network connection to test.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ReleaseInfo:
    version: str
    yanked: bool
    yanked_reason: str | None = None


class PackageRegistry(Protocol):
    def list_releases(self, package_name: str) -> list[ReleaseInfo]:
        """Returns all known releases for a package, in no particular order."""
        ...


class PyPIRegistry:
    """Looks up real release data from PyPI's JSON API
    (https://pypi.org/pypi/{name}/json) using only urllib -- no
    `requests` dependency. Network access is required to use this class;
    it is never invoked from the test suite (see InMemoryRegistry)."""

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    def list_releases(self, package_name: str) -> list[ReleaseInfo]:
        url = f"https://pypi.org/pypi/{package_name}/json"
        with urllib.request.urlopen(url, timeout=self.timeout_seconds) as resp:
            data = json.loads(resp.read())

        releases = []
        for version, files in data.get("releases", {}).items():
            if not files:
                continue  # a version with no uploaded files isn't a real release
            yanked = any(f.get("yanked", False) for f in files)
            yanked_reason = next(
                (f.get("yanked_reason") for f in files if f.get("yanked")), None
            )
            releases.append(
                ReleaseInfo(version=version, yanked=yanked, yanked_reason=yanked_reason)
            )
        return releases


class InMemoryRegistry:
    """Test fake: holds a fixed set of releases per package, supplied by
    the caller. Used throughout the test suite so version-resolution
    logic can be tested deterministically without any network access."""

    def __init__(self, releases_by_package: dict[str, list[ReleaseInfo]]) -> None:
        self._releases = releases_by_package

    def list_releases(self, package_name: str) -> list[ReleaseInfo]:
        return self._releases.get(package_name, [])
