#!/usr/bin/env python3
"""Inspect, check and repair a Phantom Troupe archive.

Stdlib only. The archive format is documented in docs/archive.md; this script is
the executable half of that document. When the two disagree, the document wins
and this script has a bug.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1

# Step identifier -> file prefix. The order of this mapping is the order of the work.
STEPS = {
    "ticket": 10,
    "refine": 20,
    "design": 30,
    "dev": 40,
    "review": 50,
    "test": 60,
    "ship": 70,
}
STEP_STATES = {"running", "done", "skipped", "failed"}
SUBJECT_STATUS = {"open", "active", "blocked", "done"}
EPIC_STATUS = {"open", "active", "done"}

RECIPROCAL = {
    "parent": "child",
    "child": "parent",
    "depends-on": "blocks",
    "blocks": "depends-on",
    "relates-to": "relates-to",
    "supersedes": "superseded-by",
    "superseded-by": "supersedes",
}

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# A subject id becomes a directory name, so it may not contain a separator or a
# parent reference. Ticket keys come from a tracker, which is not us.
SUBJECT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

DEFAULT_ARCHIVE = "~/.local/share/phantom-troupe"
CONFIG_CANDIDATES = (
    "{env}",
    ".troupe/config.json",
    "~/.config/phantom-troupe/config.json",
)


# --------------------------------------------------------------------------- io


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload) -> None:
    """Write atomically, so an interrupted run never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    tmp.replace(path)


def find_config() -> Path | None:
    env = os.environ.get("TROUPE_CONFIG")
    if env:
        candidate = Path(env).expanduser()
        return candidate if candidate.is_file() else None
    for raw in CONFIG_CANDIDATES[1:]:
        candidate = Path(raw).expanduser()
        if candidate.is_file():
            return candidate
    return None


def load_config() -> dict:
    """The configuration, or {} when there is none. Never raises on a bad file."""
    path = find_config()
    if not path:
        return {}
    try:
        return read_json(path)
    except (OSError, json.JSONDecodeError):
        return {}


def find_archive(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("TROUPE_ARCHIVE")
    if env:
        return Path(env).expanduser()
    config = find_config()
    if config:
        try:
            value = read_json(config).get("archive")
        except (OSError, json.JSONDecodeError):
            value = None
        if value:
            return Path(value).expanduser()
    return Path(DEFAULT_ARCHIVE).expanduser()


# ---------------------------------------------------------------------- loading


class Archive:
    def __init__(self, root: Path):
        self.root = root
        self.subjects: dict[str, dict] = {}
        self.epics: dict[str, dict] = {}
        self.errors: list[str] = []

    def load(self) -> "Archive":
        subjects_dir = self.root / "subjects"
        if subjects_dir.is_dir():
            for entry in sorted(subjects_dir.iterdir()):
                path = entry / "subject.json"
                if not path.is_file():
                    continue
                try:
                    data = read_json(path)
                except json.JSONDecodeError as exc:
                    self.errors.append(f"{path}: not valid JSON ({exc})")
                    continue
                data["_dir"] = entry.name
                data["_path"] = str(path)
                self.subjects[data.get("id", entry.name)] = data

        epics_dir = self.root / "epics"
        if epics_dir.is_dir():
            for path in sorted(epics_dir.glob("*.json")):
                try:
                    data = read_json(path)
                except json.JSONDecodeError as exc:
                    self.errors.append(f"{path}: not valid JSON ({exc})")
                    continue
                data["_path"] = str(path)
                self.epics[data.get("slug", path.stem)] = data
        return self

    # ------------------------------------------------------------- validation

    def validate(self) -> list[str]:
        for sid, s in sorted(self.subjects.items()):
            where = s.get("_path", sid)
            self._check_schema(s, where)

            if s.get("id") != s.get("_dir"):
                self.errors.append(
                    f"{where}: id {s.get('id')!r} does not match its directory {s.get('_dir')!r}"
                )
            for field in ("tracker", "key", "title", "status"):
                if not s.get(field):
                    self.errors.append(f"{where}: missing {field}")
            if s.get("status") not in SUBJECT_STATUS:
                self.errors.append(
                    f"{where}: status {s.get('status')!r} is not one of {sorted(SUBJECT_STATUS)}"
                )

            for name, step in (s.get("steps") or {}).items():
                if name not in STEPS:
                    self.errors.append(f"{where}: unknown step {name!r}")
                    continue
                if not isinstance(step, dict):
                    self.errors.append(f"{where}: step {name!r} is not an object")
                    continue
                if step.get("state") not in STEP_STATES:
                    self.errors.append(
                        f"{where}: step {name!r} state {step.get('state')!r} is not one of "
                        f"{sorted(STEP_STATES)}"
                    )
                if step.get("state") == "skipped" and not step.get("reason"):
                    self.errors.append(f"{where}: step {name!r} was skipped without a reason")
                target = step.get("file")
                if target and not (self.root / "subjects" / sid / target).is_file():
                    self.errors.append(f"{where}: step {name!r} points at a missing file {target}")

            self._check_links(sid, s, where)
            self._check_epic_membership(sid, s, where)

        for slug, e in sorted(self.epics.items()):
            where = e.get("_path", slug)
            self._check_schema(e, where)
            if e.get("slug") != slug or not SLUG.match(slug):
                self.errors.append(f"{where}: slug {slug!r} is not a valid slug or does not match the file name")
            if e.get("status") not in EPIC_STATUS:
                self.errors.append(
                    f"{where}: status {e.get('status')!r} is not one of {sorted(EPIC_STATUS)}"
                )
            for sid in e.get("subjects") or []:
                if sid not in self.subjects:
                    self.errors.append(f"{where}: lists unknown subject {sid!r}")
                elif self.subjects[sid].get("epic") != slug:
                    self.errors.append(
                        f"{where}: lists {sid!r}, which belongs to epic "
                        f"{self.subjects[sid].get('epic')!r}"
                    )
            narrative = e.get("narrative")
            if narrative and not (self.root / "epics" / narrative).is_file():
                self.errors.append(f"{where}: narrative file {narrative} is missing")

        return self.errors

    def _check_schema(self, obj: dict, where: str) -> None:
        version = obj.get("schema")
        if version != SCHEMA:
            self.errors.append(
                f"{where}: schema {version!r} is not {SCHEMA}; this tool cannot read it"
            )

    def _check_links(self, sid: str, s: dict, where: str) -> None:
        for link in s.get("links") or []:
            kind, other = link.get("type"), link.get("id")
            if kind not in RECIPROCAL:
                self.errors.append(f"{where}: unknown link type {kind!r}")
                continue
            if other not in self.subjects:
                self.errors.append(f"{where}: links to unknown subject {other!r}")
                continue
            wanted = RECIPROCAL[kind]
            back = self.subjects[other].get("links") or []
            if not any(l.get("type") == wanted and l.get("id") == sid for l in back):
                self.errors.append(
                    f"{where}: one-sided link {kind} -> {other}; {other} should carry "
                    f"{wanted} -> {sid} (archive.py reindex --fix-links)"
                )

    def _check_epic_membership(self, sid: str, s: dict, where: str) -> None:
        slug = s.get("epic")
        if not slug:
            return
        epic = self.epics.get(slug)
        if epic is None:
            self.errors.append(f"{where}: belongs to unknown epic {slug!r}")
        elif sid not in (epic.get("subjects") or []):
            self.errors.append(f"{where}: epic {slug!r} does not list it back")

    # ---------------------------------------------------------------- repair

    def fix_links(self) -> list[str]:
        fixed = []
        for sid, s in sorted(self.subjects.items()):
            for link in list(s.get("links") or []):
                kind, other = link.get("type"), link.get("id")
                if kind not in RECIPROCAL or other not in self.subjects:
                    continue
                wanted = RECIPROCAL[kind]
                target = self.subjects[other]
                back = target.setdefault("links", [])
                if not any(l.get("type") == wanted and l.get("id") == sid for l in back):
                    back.append({"type": wanted, "id": sid})
                    target["updatedAt"] = now()
                    fixed.append(f"{other}: added {wanted} -> {sid}")
        for slug, epic in sorted(self.epics.items()):
            members = epic.setdefault("subjects", [])
            for sid, s in sorted(self.subjects.items()):
                if s.get("epic") == slug and sid not in members:
                    members.append(sid)
                    epic["updatedAt"] = now()
                    fixed.append(f"epic {slug}: added {sid}")
        if fixed:
            self.save()
        return fixed

    def save(self) -> None:
        for sid, s in self.subjects.items():
            payload = {k: v for k, v in s.items() if not k.startswith("_")}
            write_json(self.root / "subjects" / sid / "subject.json", payload)
        for slug, e in self.epics.items():
            payload = {k: v for k, v in e.items() if not k.startswith("_")}
            write_json(self.root / "epics" / f"{slug}.json", payload)

    # ----------------------------------------------------------------- index

    def furthest_step(self, s: dict) -> tuple[str | None, int]:
        reached = [n for n in (s.get("steps") or {}) if n in STEPS]
        if not reached:
            return None, 0
        last = max(reached, key=lambda n: STEPS[n])
        return last, list(STEPS).index(last) + 1

    def build_index(self) -> dict:
        subjects = []
        for sid, s in sorted(self.subjects.items()):
            step, position = self.furthest_step(s)
            subjects.append(
                {
                    "id": sid,
                    "title": s.get("title"),
                    "status": s.get("status"),
                    "epic": s.get("epic"),
                    "step": step,
                    "stepIndex": position,
                    "stepTotal": len(STEPS),
                    "updatedAt": s.get("updatedAt"),
                }
            )
        epics = [
            {
                "slug": slug,
                "title": e.get("title"),
                "status": e.get("status"),
                "subjects": len(e.get("subjects") or []),
            }
            for slug, e in sorted(self.epics.items())
        ]
        return {
            "schema": SCHEMA,
            "generatedAt": now(),
            "subjects": subjects,
            "epics": epics,
        }


# -------------------------------------------------------------------- commands


def cmd_validate(args) -> int:
    root = find_archive(args.archive)
    if not root.is_dir():
        print(f"No archive at {root}", file=sys.stderr)
        return 1
    archive = Archive(root).load()
    errors = archive.validate()
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(f"\n{len(errors)} problem(s) in {root}", file=sys.stderr)
        return 1
    print(f"{len(archive.subjects)} subject(s), {len(archive.epics)} epic(s): no problem in {root}")
    return 0


def cmd_reindex(args) -> int:
    root = find_archive(args.archive)
    if not root.is_dir():
        print(f"No archive at {root}", file=sys.stderr)
        return 1
    archive = Archive(root).load()
    if args.fix_links:
        for line in archive.fix_links():
            print(f"fixed: {line}")
        archive = Archive(root).load()
    write_json(root / "index.json", archive.build_index())
    print(f"index.json rebuilt: {len(archive.subjects)} subject(s), {len(archive.epics)} epic(s)")
    return 0


def cmd_show(args) -> int:
    root = find_archive(args.archive)
    archive = Archive(root).load()
    if args.id:
        s = archive.subjects.get(args.id)
        if not s:
            print(f"Unknown subject {args.id!r} in {root}", file=sys.stderr)
            return 1
        print(json.dumps({k: v for k, v in s.items() if not k.startswith("_")}, indent=2, ensure_ascii=False))
        return 0
    if not archive.subjects:
        print(f"The archive at {root} is empty")
        return 0
    width = max(len(sid) for sid in archive.subjects)
    for sid, s in sorted(archive.subjects.items(), key=lambda kv: kv[1].get("updatedAt") or "", reverse=True):
        step, position = archive.furthest_step(s)
        epic = f"  [{s['epic']}]" if s.get("epic") else ""
        print(
            f"{sid:<{width}}  {s.get('status',''):<7}  "
            f"{(step or '-'):<7} {position}/{len(STEPS)}  {s.get('title','')}{epic}"
        )
    return 0


# ------------------------------------------------------------------ mutations


def check_id(sid: str) -> str:
    if not sid or ".." in sid or not SUBJECT_ID.match(sid):
        raise SystemExit(
            f"error: {sid!r} is not a usable subject id "
            "(letters, digits, dot, dash and underscore, starting with a letter or digit)"
        )
    return sid


def subject_path(root: Path, sid: str) -> Path:
    return root / "subjects" / check_id(sid) / "subject.json"


def load_subject(root: Path, sid: str) -> dict:
    path = subject_path(root, sid)
    if not path.is_file():
        raise SystemExit(f"error: unknown subject {sid!r} in {root}")
    return read_json(path)


def save_subject(root: Path, sid: str, subject: dict) -> None:
    subject["updatedAt"] = now()
    write_json(subject_path(root, sid), subject)


def refresh(root: Path) -> None:
    """Keep the derived index in step with the source of truth."""
    write_json(root / "index.json", Archive(root).load().build_index())


def cmd_new(args) -> int:
    root = find_archive(args.archive)
    sid = args.id or f"{args.tracker}-{args.key}"
    path = subject_path(root, sid)
    if path.is_file():
        if args.if_missing:
            print(sid)
            return 0
        print(f"error: {sid} already exists", file=sys.stderr)
        return 1
    subject = {
        "schema": SCHEMA,
        "id": sid,
        "tracker": args.tracker,
        "trackerKind": args.kind,
        "project": args.project,
        "key": args.key,
        "url": args.url,
        "title": args.title,
        "status": "open",
        "epic": None,
        "links": [],
        "descriptionDigest": None,
        "steps": {},
        "createdAt": now(),
        "updatedAt": now(),
    }
    (root / "subjects" / sid / "steps").mkdir(parents=True, exist_ok=True)
    write_json(path, subject)
    if args.epic:
        attach_epic(root, sid, args.epic, None)
    refresh(root)
    print(sid)
    return 0


def cmd_set(args) -> int:
    root = find_archive(args.archive)
    subject = load_subject(root, args.id)
    if args.status:
        if args.status not in SUBJECT_STATUS:
            print(f"error: status must be one of {sorted(SUBJECT_STATUS)}", file=sys.stderr)
            return 1
        subject["status"] = args.status
    for field, value in (("title", args.title), ("url", args.url), ("project", args.project)):
        if value is not None:
            subject[field] = value
    if args.digest is not None:
        subject["descriptionDigest"] = args.digest
    save_subject(root, args.id, subject)
    if args.epic:
        attach_epic(root, args.id, args.epic, None)
    refresh(root)
    print(f"{args.id} updated")
    return 0


def cmd_step(args) -> int:
    root = find_archive(args.archive)
    subject = load_subject(root, args.id)
    if args.state == "skipped" and not args.reason:
        print("error: a skipped step needs --reason", file=sys.stderr)
        return 1
    entry = {"state": args.state, "at": now()}
    for field, value in (
        ("member", args.member),
        ("file", args.file),
        ("reason", args.reason),
        ("error", args.error),
        ("verdict", args.verdict),
    ):
        if value:
            entry[field] = value
    subject.setdefault("steps", {})[args.step] = entry
    save_subject(root, args.id, subject)
    refresh(root)
    print(f"{args.id}: {args.step} -> {args.state}")
    return 0


def cmd_journal(args) -> int:
    root = find_archive(args.archive)
    load_subject(root, args.id)
    body = sys.stdin.read() if args.file == "-" else Path(args.file).expanduser().read_text(encoding="utf-8")
    heading = f"## {now()} — {args.step} — {args.member or 'chrollo'}"
    path = root / "subjects" / args.id / "journal.md"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if not existing or existing.endswith("\n\n"):
        separator = ""
    elif existing.endswith("\n"):
        separator = "\n"
    else:
        separator = "\n\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{separator}{heading}\n\n{body.strip()}\n")
    print(f"{args.id}: journal entry added")
    return 0


def cmd_current(args) -> int:
    root = find_archive(args.archive)
    root.mkdir(parents=True, exist_ok=True)
    if args.clear:
        write_json(root / "current.json", {"schema": SCHEMA, "subjectId": None})
        print("current cleared")
        return 0
    if not args.id or not args.step:
        print("error: --id and --step are required unless --clear", file=sys.stderr)
        return 1
    subject = load_subject(root, args.id)
    order = list(STEPS)
    write_json(
        root / "current.json",
        {
            "schema": SCHEMA,
            "subjectId": args.id,
            "title": subject.get("title"),
            "step": args.step,
            "stepIndex": order.index(args.step) + 1 if args.step in order else 0,
            "stepTotal": len(order),
            "member": args.member,
            "epic": subject.get("epic"),
            "startedAt": now(),
            "updatedAt": now(),
        },
    )
    print(f"current: {args.id} {args.step}")
    return 0


def cmd_link(args) -> int:
    root = find_archive(args.archive)
    if args.type not in RECIPROCAL:
        print(f"error: link type must be one of {sorted(RECIPROCAL)}", file=sys.stderr)
        return 1
    a = load_subject(root, args.id)
    b = load_subject(root, args.to)
    back = RECIPROCAL[args.type]
    if not any(l.get("type") == args.type and l.get("id") == args.to for l in a.setdefault("links", [])):
        a["links"].append({"type": args.type, "id": args.to})
    if not any(l.get("type") == back and l.get("id") == args.id for l in b.setdefault("links", [])):
        b["links"].append({"type": back, "id": args.id})
    save_subject(root, args.id, a)
    save_subject(root, args.to, b)
    refresh(root)
    print(f"{args.id} {args.type} {args.to}")
    return 0


def attach_epic(root: Path, sid: str, slug: str, title: str | None) -> None:
    if not SLUG.match(slug):
        raise SystemExit(f"error: {slug!r} is not a valid slug (lowercase, digits, hyphens)")
    path = root / "epics" / f"{slug}.json"
    epic = read_json(path) if path.is_file() else {
        "schema": SCHEMA,
        "slug": slug,
        "title": title or slug,
        "status": "open",
        "subjects": [],
        "createdAt": now(),
        "updatedAt": now(),
    }
    if title:
        epic["title"] = title
    if sid and sid not in epic["subjects"]:
        epic["subjects"].append(sid)
    epic["updatedAt"] = now()
    write_json(path, epic)
    if sid:
        subject = load_subject(root, sid)
        subject["epic"] = slug
        save_subject(root, sid, subject)


def cmd_epic(args) -> int:
    root = find_archive(args.archive)
    attach_epic(root, args.add, args.slug, args.title)
    if args.status:
        if args.status not in EPIC_STATUS:
            print(f"error: status must be one of {sorted(EPIC_STATUS)}", file=sys.stderr)
            return 1
        path = root / "epics" / f"{args.slug}.json"
        epic = read_json(path)
        epic["status"] = args.status
        epic["updatedAt"] = now()
        write_json(path, epic)
    refresh(root)
    print(f"epic {args.slug} updated")
    return 0


def cmd_digest(args) -> int:
    text = sys.stdin.read() if not args.file or args.file == "-" else Path(args.file).expanduser().read_text(encoding="utf-8")
    print(digest(text))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive", help="archive directory (default: configuration, then $TROUPE_ARCHIVE)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="check the archive against docs/archive.md").set_defaults(func=cmd_validate)

    reindex = sub.add_parser("reindex", help="rebuild index.json from the subjects")
    reindex.add_argument("--fix-links", action="store_true", help="write the missing half of one-sided links")
    reindex.set_defaults(func=cmd_reindex)

    show = sub.add_parser("show", help="print one subject, or the board")
    show.add_argument("id", nargs="?")
    show.set_defaults(func=cmd_show)

    new = sub.add_parser("new", help="create a subject")
    new.add_argument("--id")
    new.add_argument("--tracker", required=True)
    new.add_argument("--key", required=True)
    new.add_argument("--title", required=True)
    new.add_argument("--kind")
    new.add_argument("--project")
    new.add_argument("--url")
    new.add_argument("--epic")
    new.add_argument("--if-missing", action="store_true", help="succeed quietly if it already exists")
    new.set_defaults(func=cmd_new)

    setter = sub.add_parser("set", help="change a subject's fields")
    setter.add_argument("id")
    setter.add_argument("--status")
    setter.add_argument("--title")
    setter.add_argument("--url")
    setter.add_argument("--project")
    setter.add_argument("--digest")
    setter.add_argument("--epic")
    setter.set_defaults(func=cmd_set)

    step = sub.add_parser("step", help="record the outcome of a step")
    step.add_argument("id")
    step.add_argument("--step", required=True, choices=list(STEPS))
    step.add_argument("--state", required=True, choices=sorted(STEP_STATES))
    step.add_argument("--member")
    step.add_argument("--file")
    step.add_argument("--reason")
    step.add_argument("--error")
    step.add_argument("--verdict")
    step.set_defaults(func=cmd_step)

    journal = sub.add_parser("journal", help="append a block to a subject's journal")
    journal.add_argument("id")
    journal.add_argument("--step", required=True)
    journal.add_argument("--member")
    journal.add_argument("--file", required=True, help="file holding the block, or - for stdin")
    journal.set_defaults(func=cmd_journal)

    current = sub.add_parser("current", help="set or clear what the mod shows above the prompt")
    current.add_argument("--id")
    current.add_argument("--step")
    current.add_argument("--member")
    current.add_argument("--clear", action="store_true")
    current.set_defaults(func=cmd_current)

    link = sub.add_parser("link", help="link two subjects, both sides at once")
    link.add_argument("id")
    link.add_argument("--type", required=True, choices=sorted(RECIPROCAL))
    link.add_argument("--to", required=True)
    link.set_defaults(func=cmd_link)

    epic = sub.add_parser("epic", help="create an epic, or add a subject to one")
    epic.add_argument("slug")
    epic.add_argument("--title")
    epic.add_argument("--add", help="subject id to add")
    epic.add_argument("--status")
    epic.set_defaults(func=cmd_epic)

    dig = sub.add_parser("digest", help="print the sha256 digest of a description")
    dig.add_argument("--file", help="file to read, or - for stdin")
    dig.set_defaults(func=cmd_digest)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
