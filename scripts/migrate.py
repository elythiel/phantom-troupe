#!/usr/bin/env python3
"""Import an older per-ticket directory layout into a Fantome Troupe archive.

Plenty of hand-rolled agent setups keep one directory per ticket, holding a few
Markdown files named after whoever wrote them. This maps those files onto the
archive's steps.

It prints what it would do and changes nothing until you pass --apply. It never
deletes or moves anything from the source: it copies.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from archive import SCHEMA, STEPS, find_archive, now, write_json  # noqa: E402

# Source file name (lowercase, without extension) -> step identifier.
# "journal" is not a step: the file is appended to journal.md instead.
DEFAULT_MAP = {
    "story": "ticket",
    "ticket": "ticket",
    "po-review": "refine",
    "requirements": "refine",
    "refine": "refine",
    "ux-review": "design",
    "design": "design",
    "dev-challenge": "dev",
    "mr-description": "dev",
    "implementation": "dev",
    "code-review": "review",
    "review": "review",
    "test-report": "test",
    "tests": "test",
    "ship": "ship",
    "release": "ship",
    "summary": "journal",
}

ATTACHMENTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".pdf"}


def step_file(step: str) -> str:
    return f"steps/{STEPS[step]}-{step}.md"


def plan_subject(source: Path, tracker: str, project: str | None, mapping: dict) -> dict | None:
    key = source.name
    moves: list[tuple[Path, str]] = []
    journal: list[Path] = []
    attachments: list[Path] = []
    unmatched: list[Path] = []

    for item in sorted(source.iterdir()):
        if item.is_dir() or item.name.startswith("."):
            continue
        stem = item.stem.lower()
        suffix = item.suffix.lower()
        if suffix in ATTACHMENTS:
            attachments.append(item)
            continue
        target = mapping.get(stem)
        if target == "journal":
            journal.append(item)
        elif target:
            moves.append((item, step_file(target)))
        else:
            unmatched.append(item)

    if not moves and not journal and not attachments:
        return None

    title = ""
    for candidate, _ in moves:
        if candidate.stem.lower() in ("story", "ticket"):
            for line in candidate.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip().lstrip("#").strip()
                if line:
                    title = line[:120]
                    break
            break

    return {
        "id": f"{tracker}-{key}",
        "key": key,
        "title": title or key,
        "project": project,
        "moves": moves,
        "journal": journal,
        "attachments": attachments,
        "unmatched": unmatched,
    }


def apply_subject(root: Path, tracker: str, plan: dict) -> None:
    sid = plan["id"]
    target = root / "subjects" / sid
    (target / "steps").mkdir(parents=True, exist_ok=True)

    steps: dict[str, dict] = {}
    for item, relative in plan["moves"]:
        destination = target / relative
        shutil.copyfile(item, destination)
        name = relative.split("-", 1)[1][:-3]
        steps[name] = {"state": "done", "at": now(), "file": relative, "imported": item.name}

    if plan["attachments"]:
        (target / "attachments").mkdir(exist_ok=True)
        for item in plan["attachments"]:
            shutil.copyfile(item, target / "attachments" / item.name)

    journal = target / "journal.md"
    blocks = []
    for item in plan["journal"]:
        body = item.read_text(encoding="utf-8", errors="replace").strip()
        blocks.append(f"## {now()} — imported — {item.name}\n\n{body}\n")
    if blocks:
        with journal.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(blocks) + "\n")

    subject = {
        "schema": SCHEMA,
        "id": sid,
        "tracker": tracker,
        "trackerKind": None,
        "project": plan["project"],
        "key": plan["key"],
        "url": None,
        "title": plan["title"],
        "status": "done",
        "epic": None,
        "links": [],
        "descriptionDigest": None,
        "steps": steps,
        "createdAt": now(),
        "updatedAt": now(),
        "importedFrom": "legacy directory layout",
    }
    write_json(target / "subject.json", subject)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True, help="directory holding one subdirectory per ticket")
    parser.add_argument("--tracker", required=True, help="tracker name to file these subjects under")
    parser.add_argument("--project", help="project alias to record on each subject")
    parser.add_argument("--archive", help="target archive directory")
    parser.add_argument("--map", help="JSON file overriding the file-name to step mapping")
    parser.add_argument("--match", default=r".+", help="only import directories whose name matches this regex")
    parser.add_argument("--apply", action="store_true", help="actually write; without it nothing changes")
    args = parser.parse_args()

    source = Path(args.source).expanduser()
    if not source.is_dir():
        print(f"No such directory: {source}", file=sys.stderr)
        return 1

    mapping = dict(DEFAULT_MAP)
    if args.map:
        mapping.update(json.loads(Path(args.map).expanduser().read_text(encoding="utf-8")))

    root = find_archive(args.archive)
    pattern = re.compile(args.match)

    plans = []
    for entry in sorted(source.iterdir()):
        if not entry.is_dir() or not pattern.match(entry.name):
            continue
        plan = plan_subject(entry, args.tracker, args.project, mapping)
        if plan:
            plans.append(plan)

    if not plans:
        print(f"Nothing to import from {source}")
        return 0

    print(f"{'Importing' if args.apply else 'Would import'} {len(plans)} subject(s) into {root}\n")
    for plan in plans:
        existing = (root / "subjects" / plan["id"]).exists()
        print(f"  {plan['id']}  {plan['title']}" + ("   [already in the archive, skipped]" if existing else ""))
        for item, relative in plan["moves"]:
            print(f"      {item.name}  ->  {relative}")
        for item in plan["journal"]:
            print(f"      {item.name}  ->  journal.md")
        for item in plan["attachments"]:
            print(f"      {item.name}  ->  attachments/{item.name}")
        for item in plan["unmatched"]:
            print(f"      {item.name}  ->  (no mapping, left behind)")
        print()

    if not args.apply:
        print("Nothing was written. Re-run with --apply to do it.")
        return 0

    written = 0
    for plan in plans:
        if (root / "subjects" / plan["id"]).exists():
            continue
        apply_subject(root, args.tracker, plan)
        written += 1
    print(f"{written} subject(s) written. Run scripts/archive.py reindex next.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
