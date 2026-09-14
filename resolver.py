"""Given an alert and the current requirements.txt pin, decides what
version to move to -- or that there's nothing to do.

Decision policy:
  1. If the currently pinned version isn't in the alert's vulnerable
     range, do nothing (already safe, or the alert doesn't apply to the
     pinned version).
  2. If the alert names a first_patched_version, prefer it -- but only
     if the registry confirms that release exists and hasn't been
     yanked. A yanked "fix" is not a fix.
  3. If first_patched_version is missing, yanked, or unavailable, fall
     back to the lowest release that is (a) strictly greater than the
     currently pinned version and (b) NOT in the vulnerable range and
     (c) not yanked. This is the "check package docs" step when the
     alert itself doesn't hand us a clean answer.
  4. If no such release exists, report that no fix could be resolved
     rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from depfix.alerts import DependabotAlert
from depfix.registry import PackageRegistry
from depfix.version import InvalidVersionError, parse_version, version_satisfies


@dataclass
class Resolution:
    package_name: str
    alert_number: int
    current_version: Optional[str]
    target_version: Optional[str]
    reason: str


def resolve(
    alert: DependabotAlert, current_version: Optional[str], registry: PackageRegistry
) -> Resolution:
    if current_version is None:
        return Resolution(
            package_name=alert.package_name,
            alert_number=alert.number,
            current_version=None,
            target_version=None,
            reason="package not found in requirements.txt",
        )

    try:
        currently_vulnerable = version_satisfies(
            current_version, alert.vulnerable_version_range
        )
    except InvalidVersionError as exc:
        return Resolution(
            package_name=alert.package_name,
            alert_number=alert.number,
            current_version=current_version,
            target_version=None,
            reason=f"could not evaluate vulnerable range: {exc}",
        )

    if not currently_vulnerable:
        return Resolution(
            package_name=alert.package_name,
            alert_number=alert.number,
            current_version=current_version,
            target_version=None,
            reason="pinned version is not affected by this alert",
        )

    releases = {r.version: r for r in registry.list_releases(alert.package_name)}

    if alert.first_patched_version is not None:
        patched = releases.get(alert.first_patched_version)
        if patched is not None and not patched.yanked:
            return Resolution(
                package_name=alert.package_name,
                alert_number=alert.number,
                current_version=current_version,
                target_version=alert.first_patched_version,
                reason="upgraded to the advisory's first_patched_version",
            )

    # Fall back to the lowest safe, non-yanked release above the current
    # pin -- this is the "check package docs" step kicking in when the
    # alert alone doesn't give us a usable answer.
    candidates = []
    for release in releases.values():
        if release.yanked:
            continue
        try:
            if version_satisfies(release.version, alert.vulnerable_version_range):
                continue
            if not (parse_version(release.version) > parse_version(current_version)):
                continue
        except InvalidVersionError:
            continue
        candidates.append(release.version)

    if not candidates:
        return Resolution(
            package_name=alert.package_name,
            alert_number=alert.number,
            current_version=current_version,
            target_version=None,
            reason="no safe, non-yanked release found on the registry",
        )

    best = min(candidates, key=parse_version)
    return Resolution(
        package_name=alert.package_name,
        alert_number=alert.number,
        current_version=current_version,
        target_version=best,
        reason="advisory's patched version unavailable/yanked; "
        "picked the lowest safe release instead",
    )
