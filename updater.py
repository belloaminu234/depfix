"""Ties the pieces together: parse alerts, parse requirements.txt,
resolve a target version per alert, and (optionally) rewrite
requirements.txt with the fixes applied.
"""

from __future__ import annotations

from dataclasses import dataclass

from depfix.alerts import DependabotAlert
from depfix.registry import PackageRegistry
from depfix.requirements import (
    RequirementLine,
    bump_version,
    normalize_name,
    render_requirements,
)
from depfix.resolver import Resolution, resolve


@dataclass
class UpdateResult:
    resolutions: list[Resolution]
    updated_text: str
    changed: bool


def apply_alerts(
    requirements_text: str,
    alerts: list[DependabotAlert],
    registry: PackageRegistry,
) -> UpdateResult:
    from depfix.requirements import parse_requirements

    lines = parse_requirements(requirements_text)
    current_versions = {
        line.name: line.version for line in lines if line.name is not None
    }

    resolutions: list[Resolution] = []
    any_change = False

    for alert in alerts:
        if alert.ecosystem != "pip":
            resolutions.append(
                Resolution(
                    package_name=alert.package_name,
                    alert_number=alert.number,
                    current_version=None,
                    target_version=None,
                    reason=f"unsupported ecosystem {alert.ecosystem!r}; only pip is handled",
                )
            )
            continue

        if alert.state != "open":
            resolutions.append(
                Resolution(
                    package_name=alert.package_name,
                    alert_number=alert.number,
                    current_version=None,
                    target_version=None,
                    reason=f"alert state is {alert.state!r}, not 'open'; skipped",
                )
            )
            continue

        normalized = normalize_name(alert.package_name)
        current = current_versions.get(normalized)
        resolution = resolve(alert, current, registry)
        resolutions.append(resolution)

        if resolution.target_version is not None:
            lines, changed = bump_version(lines, alert.package_name, resolution.target_version)
            any_change = any_change or changed

    return UpdateResult(
        resolutions=resolutions,
        updated_text=render_requirements(lines),
        changed=any_change,
    )
