#!/usr/bin/env python3
"""Talk to a Vikunja tracker through the vocabulary the troupe uses.

One subcommand per operation in skills/tracker/SKILL.md, each printing JSON on stdout.
The point of this script is that three Vikunja rules are easy to get wrong by
hand and impossible to get wrong here: an update sends the complete task,
descriptions are HTML, and moving a card goes through the kanban view's buckets.

Only the `vikunja` adapter lives here. A `jira-mcp` tracker is reached through
the session's Atlassian MCP tools, which a script cannot call.

The token is read from the file the configuration names and is never printed,
logged, or written anywhere.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from archive import load_config  # noqa: E402

TIMEOUT = 30


class TrackerError(RuntimeError):
    pass


# ------------------------------------------------------------------ resolution


def resolve(name: str | None) -> tuple[str, dict]:
    config = load_config()
    trackers = config.get("trackers") or {}
    if not trackers:
        raise TrackerError("No tracker is configured. See docs/configuration.md.")
    chosen = name or config.get("defaultTracker")
    if not chosen:
        raise TrackerError("No --tracker given and no defaultTracker in the configuration.")
    if chosen not in trackers:
        raise TrackerError(f"Unknown tracker {chosen!r}. Configured: {', '.join(sorted(trackers))}.")
    tracker = trackers[chosen]
    kind = tracker.get("kind")
    if kind != "vikunja":
        raise TrackerError(
            f"Tracker {chosen!r} is of kind {kind!r}; this script only speaks vikunja. "
            "Use the session's MCP tools for it."
        )
    for field in ("baseUrl", "tokenFile"):
        if not tracker.get(field):
            raise TrackerError(f"Tracker {chosen!r} has no {field}.")
    return chosen, tracker


def token_of(tracker: dict) -> str:
    path = Path(tracker["tokenFile"]).expanduser()
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise TrackerError(f"Cannot read the token file ({exc.strerror}).") from None
    if not value:
        raise TrackerError("The token file is empty.")
    return value


def project_id(tracker: dict, alias: str | None) -> int:
    projects = tracker.get("projects") or {}
    key = alias or tracker.get("defaultProject")
    if key is None:
        raise TrackerError("No project given and no defaultProject on this tracker.")
    if isinstance(key, int) or str(key).isdigit():
        return int(key)
    if key not in projects:
        raise TrackerError(f"Unknown project {key!r}. Configured: {', '.join(sorted(projects))}.")
    return int(projects[key])


# ------------------------------------------------------------------- transport


def call(tracker: dict, method: str, path: str, payload=None):
    url = tracker["baseUrl"].rstrip("/") + path
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Authorization", "Bearer " + token_of(tracker))
    request.add_header("Accept", "application/json")
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise TrackerError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise TrackerError(f"{method} {path} could not reach the server: {exc.reason}") from None
    return json.loads(raw) if raw.strip() else None


# -------------------------------------------------------------------- kanban


def kanban_view(tracker: dict, pid: int) -> int:
    views = call(tracker, "GET", f"/projects/{pid}/views") or []
    for view in views:
        if view.get("view_kind") == "kanban" or view.get("viewKind") == "kanban":
            return int(view["id"])
    raise TrackerError(f"Project {pid} has no kanban view, so there is nothing to move a card in.")


def buckets(tracker: dict, pid: int, view: int) -> list[dict]:
    return call(tracker, "GET", f"/projects/{pid}/views/{view}/buckets") or []


def state_of(tracker: dict, task: dict) -> str:
    """Which configured state the task's bucket belongs to, or 'unknown'."""
    if task.get("done"):
        return "done"
    try:
        pid = int(task["project_id"])
        view = kanban_view(tracker, pid)
        holder = None
        for bucket in buckets(tracker, pid, view):
            if any(int(t.get("id", -1)) == int(task["id"]) for t in bucket.get("tasks") or []):
                holder = bucket.get("title", "")
                break
    except (TrackerError, KeyError, TypeError):
        return "unknown"
    if holder is None:
        return "unknown"
    for state, labels in (tracker.get("states") or {}).items():
        if any(str(label).strip().lower() == holder.strip().lower() for label in labels):
            return state
    return "unknown"


def bucket_for_state(tracker: dict, pid: int, view: int, state: str) -> dict:
    labels = [str(l).strip().lower() for l in (tracker.get("states") or {}).get(state, [])]
    if not labels:
        raise TrackerError(f"State {state!r} has no labels configured for this tracker.")
    for bucket in buckets(tracker, pid, view):
        if bucket.get("title", "").strip().lower() in labels:
            return bucket
    raise TrackerError(
        f"No bucket on project {pid} matches state {state!r} ({', '.join(labels)}). "
        "Check the tracker's states in your configuration."
    )


# ------------------------------------------------------------------ normalize


def normalize(tracker: dict, name: str, task: dict, with_state: bool = True) -> dict:
    return {
        "tracker": name,
        "kind": "vikunja",
        "key": str(task.get("id")),
        "id": f"{name}-{task.get('id')}",
        "title": task.get("title"),
        "description": task.get("description") or "",
        "state": state_of(tracker, task) if with_state else None,
        "done": bool(task.get("done")),
        "project": task.get("project_id"),
        "url": None,
        "updated": task.get("updated"),
    }


# ------------------------------------------------------------------- commands


def cmd_get(args, name, tracker):
    task = call(tracker, "GET", f"/tasks/{args.key}")
    return normalize(tracker, name, task)


def cmd_find(args, name, tracker):
    pid = project_id(tracker, args.project)
    tasks = call(tracker, "GET", f"/projects/{pid}/tasks?per_page={args.limit}") or []
    needle = (args.query or "").strip().lower()
    if needle:
        tasks = [t for t in tasks if needle in (t.get("title") or "").lower()]
    return [normalize(tracker, name, t, with_state=False) for t in tasks]


def cmd_create(args, name, tracker):
    pid = project_id(tracker, args.project)
    payload = {"title": args.title, "description": read_body(args.description_file)}
    task = call(tracker, "PUT", f"/projects/{pid}/tasks", payload)
    return normalize(tracker, name, task, with_state=False)


def cmd_update(args, name, tracker):
    # Vikunja replaces the task with what it is sent: read it, change it, send it whole.
    task = call(tracker, "GET", f"/tasks/{args.key}")
    if args.title:
        task["title"] = args.title
    if args.description_file:
        task["description"] = read_body(args.description_file)
    updated = call(tracker, "POST", f"/tasks/{args.key}", task)
    return normalize(tracker, name, updated or task, with_state=False)


def cmd_move(args, name, tracker):
    task = call(tracker, "GET", f"/tasks/{args.key}")
    pid = int(task["project_id"])
    view = kanban_view(tracker, pid)
    bucket = bucket_for_state(tracker, pid, view, args.state)
    call(
        tracker,
        "POST",
        f"/projects/{pid}/views/{view}/buckets/{bucket['id']}/tasks",
        {"task_id": int(args.key)},
    )
    return {"key": str(args.key), "movedTo": bucket.get("title"), "state": args.state}


def cmd_comment(args, name, tracker):
    created = call(tracker, "PUT", f"/tasks/{args.key}/comments", {"comment": read_body(args.file)})
    return {"key": str(args.key), "commentId": (created or {}).get("id")}


def cmd_comments(args, name, tracker):
    found = call(tracker, "GET", f"/tasks/{args.key}/comments") or []
    return [
        {"id": c.get("id"), "created": c.get("created"), "comment": c.get("comment")}
        for c in found
    ]


def cmd_states(args, name, tracker):
    pid = project_id(tracker, args.project)
    view = kanban_view(tracker, pid)
    configured = tracker.get("states") or {}
    rows = []
    for bucket in buckets(tracker, pid, view):
        title = bucket.get("title", "")
        state = next(
            (s for s, labels in configured.items()
             if any(str(l).strip().lower() == title.strip().lower() for l in labels)),
            None,
        )
        rows.append({"bucket": title, "id": bucket.get("id"), "state": state, "limit": bucket.get("limit")})
    return rows


def read_body(path: str | None) -> str:
    if not path:
        return ""
    if path == "-":
        return sys.stdin.read()
    return Path(path).expanduser().read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tracker", help="tracker name (default: defaultTracker)")
    sub = parser.add_subparsers(dest="command", required=True)

    get = sub.add_parser("get", help="one ticket, normalized")
    get.add_argument("key")
    get.set_defaults(func=cmd_get)

    find = sub.add_parser("find", help="tickets of a project, optionally filtered by title")
    find.add_argument("--project")
    find.add_argument("--query")
    find.add_argument("--limit", type=int, default=50)
    find.set_defaults(func=cmd_find)

    create = sub.add_parser("create", help="create a ticket")
    create.add_argument("--project")
    create.add_argument("--title", required=True)
    create.add_argument("--description-file", help="file holding the description, or - for stdin")
    create.set_defaults(func=cmd_create)

    update = sub.add_parser("update", help="change a ticket's title or description")
    update.add_argument("key")
    update.add_argument("--title")
    update.add_argument("--description-file", help="file holding the description, or - for stdin")
    update.set_defaults(func=cmd_update)

    move = sub.add_parser("move", help="move a card to the bucket of a configured state")
    move.add_argument("key")
    move.add_argument("--state", required=True, choices=["todo", "doing", "review", "done"])
    move.set_defaults(func=cmd_move)

    comment = sub.add_parser("comment", help="post a comment")
    comment.add_argument("key")
    comment.add_argument("--file", required=True, help="file holding the comment, or - for stdin")
    comment.set_defaults(func=cmd_comment)

    comments = sub.add_parser("comments", help="list a ticket's comments")
    comments.add_argument("key")
    comments.set_defaults(func=cmd_comments)

    states = sub.add_parser("states", help="show the project's buckets and which state each maps to")
    states.add_argument("--project")
    states.set_defaults(func=cmd_states)

    args = parser.parse_args()
    try:
        name, tracker = resolve(args.tracker)
        print(json.dumps(args.func(args, name, tracker), indent=2, ensure_ascii=False))
    except TrackerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
