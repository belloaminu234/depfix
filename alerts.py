"""Parses Dependabot security alerts, in the same shape GitHub's REST API
returns from `GET /repos/{owner}/{repo}/dependabot/alerts`. Only the pip
ecosystem is in scope for this project -- other ecosystems are skipped
with a clear reason rather than mishandled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class DependabotAlert:
    number: int
    state: str
    ecosystem: str
    package_name: str
    severity: str
    ghsa_id: str
    summary: str
    vulnerable_version_range: str
    first_patched_version: Optional[str]


def parse_alert(raw: dict[str, Any]) -> DependabotAlert:
    dependency = raw["dependency"]
    package = dependency["package"]
    vuln = raw["security_vulnerability"]
    advisory = raw["security_advisory"]

    first_patched = vuln.get("first_patched_version")
    first_patched_version = first_patched["identifier"] if first_patched else None

    return DependabotAlert(
        number=raw["number"],
        state=raw["state"],
        ecosystem=package["ecosystem"],
        package_name=package["name"],
        severity=vuln["severity"],
        ghsa_id=advisory["ghsa_id"],
        summary=advisory["summary"],
        vulnerable_version_range=vuln["vulnerable_version_range"],
        first_patched_version=first_patched_version,
    )


def parse_alerts(raw_alerts: list[dict[str, Any]]) -> list[DependabotAlert]:
    return [parse_alert(a) for a in raw_alerts]
