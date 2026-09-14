"""CLI: python -m depfix --requirements requirements.txt --alerts alerts.json [--dry-run]

`alerts.json` is a JSON array in the same shape returned by GitHub's
`GET /repos/{owner}/{repo}/dependabot/alerts` endpoint.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
from pathlib import Path

from depfix.alerts import parse_alerts
from depfix.registry import PyPIRegistry
from depfix.updater import apply_alerts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resolve Dependabot alerts and update requirements.txt."
    )
    parser.add_argument("--requirements", required=True, type=Path)
    parser.add_argument("--alerts", required=True, type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolution report without writing requirements.txt.",
    )
    args = parser.parse_args(argv)

    if not args.requirements.exists():
        print(f"error: {args.requirements} does not exist", file=sys.stderr)
        return 1
    if not args.alerts.exists():
        print(f"error: {args.alerts} does not exist", file=sys.stderr)
        return 1

    requirements_text = args.requirements.read_text()

    try:
        raw_alerts = json.loads(args.alerts.read_text())
    except json.JSONDecodeError as exc:
        print(f"error: {args.alerts} is not valid JSON: {exc}", file=sys.stderr)
        return 1

    alerts = parse_alerts(raw_alerts)
    registry = PyPIRegistry()

    try:
        result = apply_alerts(requirements_text, alerts, registry)
    except urllib.error.URLError as exc:
        print(f"error: could not reach the package registry: {exc}", file=sys.stderr)
        return 1

    for r in result.resolutions:
        if r.target_version is not None:
            print(f"[fixed] {r.package_name}: {r.current_version} -> {r.target_version}  ({r.reason})")
        else:
            print(f"[skip]  alert #{r.alert_number} {r.package_name}: {r.reason}")

    if result.changed and not args.dry_run:
        args.requirements.write_text(result.updated_text)
        print(f"\nUpdated {args.requirements}")
    elif result.changed:
        print("\n--dry-run: requirements.txt not written")
    else:
        print("\nNo changes needed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
