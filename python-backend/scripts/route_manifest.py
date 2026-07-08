"""Dump/diff the Flask URL map + Socket.IO event names.

Safety net for the codebase reorganization: proves that moving code between
modules never adds, removes, or changes a public route or socket event.

Usage (run from python-backend/):
  python scripts/route_manifest.py                                  # print manifest JSON
  python scripts/route_manifest.py --write scripts/route_manifest.baseline.json
  python scripts/route_manifest.py --diff  scripts/route_manifest.baseline.json

--diff exits 1 if any (rule, methods) pair or socket event was added/removed.
Endpoint-name changes (e.g. "health_check" -> "system.health_check") are
printed as INFO but do not fail: blueprint moves rename endpoints while URLs
stay identical, which is exactly what the reorganization is allowed to do.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Ensure imports resolve when invoked as `python scripts/route_manifest.py`.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SKIP_DIRS = {"venv", ".venv", "__pycache__", "node_modules", ".git", "uploads"}


def http_manifest():
    # Importing app boots the full application (Mongo connect included).
    # Background jobs honor this flag from the app-factory step onward.
    os.environ.setdefault("GENHIRE_DISABLE_JOBS", "1")
    from app import app

    rows = []
    for rule in app.url_map.iter_rules():
        methods = sorted(m for m in rule.methods if m not in ("HEAD", "OPTIONS"))
        rows.append({"rule": rule.rule, "methods": methods, "endpoint": rule.endpoint})
    return sorted(rows, key=lambda r: (r["rule"], r["methods"]))


def socket_manifest():
    # Static scan: handlers move between files during the migration, so grep
    # the tree instead of introspecting the server object.
    events = set()
    pattern = re.compile(r"@socketio\.on\(\s*['\"]([^'\"]+)['\"]")
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in pattern.finditer(text):
            events.add(match.group(1))
    return sorted(events)


def build_manifest():
    return {"http": http_manifest(), "socket_events": socket_manifest()}


def diff_manifests(baseline, current):
    """Return (breaking_changes, info_notes)."""
    breaking = []
    info = []

    base_rules = {(r["rule"], tuple(r["methods"])): r["endpoint"] for r in baseline["http"]}
    cur_rules = {(r["rule"], tuple(r["methods"])): r["endpoint"] for r in current["http"]}

    for key in sorted(base_rules.keys() - cur_rules.keys()):
        breaking.append(f"REMOVED route: {key[0]} {list(key[1])}")
    for key in sorted(cur_rules.keys() - base_rules.keys()):
        breaking.append(f"ADDED route: {key[0]} {list(key[1])}")
    for key in sorted(base_rules.keys() & cur_rules.keys()):
        if base_rules[key] != cur_rules[key]:
            info.append(
                f"endpoint renamed: {key[0]} {list(key[1])}: "
                f"{base_rules[key]} -> {cur_rules[key]}"
            )

    base_events = set(baseline["socket_events"])
    cur_events = set(current["socket_events"])
    for event in sorted(base_events - cur_events):
        breaking.append(f"REMOVED socket event: {event}")
    for event in sorted(cur_events - base_events):
        breaking.append(f"ADDED socket event: {event}")

    return breaking, info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", metavar="PATH", help="write manifest JSON to PATH")
    parser.add_argument("--diff", metavar="PATH", help="diff current manifest against baseline at PATH")
    args = parser.parse_args()

    current = build_manifest()

    if args.diff:
        baseline = json.loads(Path(args.diff).read_text(encoding="utf-8"))
        breaking, info = diff_manifests(baseline, current)
        for note in info:
            print(f"INFO  {note}")
        if breaking:
            for change in breaking:
                print(f"BREAK {change}")
            print(f"\nFAIL: {len(breaking)} breaking change(s) vs {args.diff}")
            sys.exit(1)
        print(
            f"OK: {len(current['http'])} routes, "
            f"{len(current['socket_events'])} socket events match {args.diff}"
        )
        return

    payload = json.dumps(current, indent=2)
    if args.write:
        Path(args.write).write_text(payload + "\n", encoding="utf-8")
        print(
            f"Wrote {len(current['http'])} routes, "
            f"{len(current['socket_events'])} socket events to {args.write}"
        )
    else:
        print(payload)


if __name__ == "__main__":
    main()
