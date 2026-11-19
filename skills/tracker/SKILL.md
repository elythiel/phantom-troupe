---
name: tracker
description: Read and write tickets on whichever issue tracker the user configured, through one vocabulary that hides Vikunja and Jira behind it. Load this before any ticket operation - reading a ticket, creating one, rewriting its description, moving its card, posting a comment - and whenever you need to work out which tracker a key belongs to.
---

# Tracker

Every ticket operation in this plugin goes through the vocabulary below. Nothing else in the
plugin talks to a tracker: the members work on files in the archive, and the orchestrator is the
only one that reaches the outside world.

Two adapters exist. Which one applies comes from the configuration, never from a guess.

## Resolve the tracker first

Read the configuration as `docs/configuration.md` describes: `$TROUPE_CONFIG`, then
`.troupe/config.json` in the project, then `~/.config/phantom-troupe/config.json`. If there is
none, stop and say what to create. Never invent a host or a project id.

Then pick the tracker, in this order:

1. an explicit `--tracker=<name>` in what the user asked;
2. the `workspaces` entry whose path is the longest prefix of the working directory;
3. the tracker whose `keyPattern` matches the ticket key you were given — if two match, ask,
   do not choose;
4. `defaultTracker`.

Say which tracker you resolved and why, in one clause, the first time you use it in a session.

## The vocabulary

| Operation | Meaning |
| --- | --- |
| `get(key)` | One ticket, normalized. |
| `find(project, query)` | Tickets of a project, optionally filtered by title. |
| `create(project, title, description)` | A new ticket. Returns its key. |
| `update(key, title?, description?)` | Change a ticket's title or description. |
| `move(key, state)` | Move the card to `todo`, `doing`, `review` or `done`. |
| `comment(key, body)` | Post a comment. |
| `comments(key)` | List comments, oldest first. |
| `states(project)` | The project's columns and which configured state each maps to. |

A normalized ticket:

```json
{
  "tracker": "personal", "kind": "vikunja", "key": "62", "id": "personal-62",
  "title": "...", "description": "...", "state": "doing", "done": false,
  "project": 1, "url": null, "updated": "2026-11-19T09:00:00Z"
}
```

`state` is one of `todo`, `doing`, `review`, `done`, `unknown` — a state **as your configuration
names it**, not as the tracker spells it. `unknown` means the card sits in a column no configured
state claims; report that rather than papering over it.

## Adapter `vikunja`

Use `${CLAUDE_PLUGIN_ROOT}/scripts/tracker.py`. It prints JSON on stdout and a one-line reason on
stderr with exit code 1. Do not hand-roll these calls: the script exists because three Vikunja
rules are easy to break by hand.

```sh
scripts/tracker.py [--tracker NAME] get <key>
scripts/tracker.py find --project <alias> --query <text>
scripts/tracker.py create --project <alias> --title <title> --description-file <file>
scripts/tracker.py update <key> [--title <title>] [--description-file <file>]
scripts/tracker.py move <key> --state doing
scripts/tracker.py comment <key> --file <file>
scripts/tracker.py comments <key>
scripts/tracker.py states --project <alias>
```

Pass bodies as files, never as arguments: a description is HTML full of quotes and angle
brackets, and a shell will mangle it. `-` reads standard input.

## Adapter `jira-mcp`

Use the session's Atlassian MCP tools. Their names carry a session-specific prefix; the
operations are the ones below. If an operation is not in your tool list, find it with the
connector's `discover` and run it with the matching execute-family tool.

| Operation | Atlassian MCP |
| --- | --- |
| `get` | `getJiraIssue` |
| `find` | `searchJiraIssuesUsingJql` |
| `create` | `createJiraIssue` |
| `update` | `editJiraIssue` |
| `move` | `transitionJiraIssue` |
| `comment` | `addOrEditJiraIssueComment` |
| `comments` | `listJiraIssueComments` |

Resolve the cloud id once per session, from the tracker's `cloudId` when it is not `auto`,
otherwise from `getAccessibleAtlassianResources`, and reuse it.

Refuse to touch an issue whose project key is not in the tracker's `projectKeys`. That list is
the blast radius, and it is the only thing standing between a wrong key and a write to the wrong
project.

`transitionJiraIssue` takes a transition, not a state. Read the issue's available transitions
and pick the one that lands in a status the tracker's `states` maps to the state you want. If
none does, say so and leave the issue where it is.

## Who is allowed to move a card

Never move a card because the work moved on. Move it only where the tracker's `transitions`
allows, and only at the moment that key names:

- `transitions.start` — entering implementation;
- `transitions.review` — the review is delivered;
- `transitions.finish` — the shipping texts are written.

A `null` means the user moves that one themselves. Honour it silently; do not offer to do it
anyway.

## Descriptions

`descriptionFormat` says what a description must be written in:

- **`html`** (Vikunja) — simple HTML: `<p>`, `<ul><li>`, `<strong>`, `<code>`. Not Markdown;
  Markdown renders as literal text. `<h2>` reads badly in a card, so use
  `<p><strong>…</strong></p>` for a heading.
- **`adf`** (Jira Cloud) — Atlassian Document Format. Build the document, do not paste Markdown.
- **`markdown`** — as written.

## Pitfalls

- **Vikunja replaces, it does not patch.** An update sends the whole task. `tracker.py update`
  reads the task, changes the fields and sends it back; a hand-written partial `POST` silently
  blanks whatever it left out. The same is true of views and buckets.
- **A full bucket refuses the card** (Vikunja error 10004) when the column has a limit. Report
  it; do not retry into another column.
- **A ticket's description can change under you.** Before acting on a refinement, compare the
  live description against the subject's `descriptionDigest`. A mismatch means the refinement is
  stale.
- **macOS ships bash 3.2.** Anything past two commands belongs in a Python script in the
  scratchpad, not in a shell one-liner.

## Secrets

The token is read from the file `tokenFile` names, by the script, at the moment of the call. Do
not read it yourself, do not pass it on a command line, do not echo it, do not write it to the
archive, and do not include it in anything you show the user. If a tracker call fails for
authentication, say that it failed; do not print what you sent.
