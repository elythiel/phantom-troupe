# The archive

The archive is the troupe's memory: what was done on a subject, by whom, when, and how subjects
relate to each other. It lives outside this repository, at the path `archive` names in your
configuration.

## Layout

```
<archive>/
├── index.json                   derived, rebuildable
├── current.json                 what the mod shows above the prompt
├── epics/
│   ├── <slug>.json              epic metadata
│   └── <slug>.md                epic narrative, optional
└── subjects/
    └── <tracker>-<key>/
        ├── subject.json         the subject's state
        ├── journal.md           append-only, chronological
        └── steps/
            ├── 10-ticket.md
            ├── 20-refine.md
            ├── 30-design.md
            ├── 40-dev.md
            ├── 50-review.md
            ├── 60-test.md
            └── 70-ship.md
```

**`subject.json` and the epic files are the source of truth. `index.json` and `current.json` are
derived** and can be deleted at any time: `scripts/archive.py reindex` rebuilds them by walking
`subjects/`. Nothing is ever only in the index.

That split exists so the mod can read one small file instead of hundreds, without becoming a
second source of truth that could disagree with the first.

## Identifiers

A subject's id is `<tracker>-<key>`, where `<tracker>` is the name you gave the tracker in your
configuration and `<key>` is the ticket key as the tracker spells it: `personal-62`,
`work-ABC-1234`. The id is also the directory name, so two trackers can hold the same key
without colliding.

An epic's id is a slug: lowercase, ASCII, words joined by hyphens.

## `subject.json`

```json
{
  "schema": 1,
  "id": "personal-62",
  "tracker": "personal",
  "trackerKind": "vikunja",
  "project": "my-project",
  "key": "62",
  "url": "https://vikunja.example.org/tasks/62",
  "title": "Attachment panel",
  "status": "active",
  "epic": "attachments",
  "links": [
    { "type": "depends-on", "id": "personal-58" }
  ],
  "descriptionDigest": "sha256:1f3a…",
  "steps": {
    "refine": {
      "state": "done",
      "member": "pakunoda",
      "at": "2026-11-19T09:12:04Z",
      "file": "steps/20-refine.md"
    },
    "design": {
      "state": "skipped",
      "at": "2026-11-19T09:12:30Z",
      "reason": "no interface in scope"
    }
  },
  "createdAt": "2026-11-18T16:00:00Z",
  "updatedAt": "2026-11-19T09:12:30Z"
}
```

| Field | Meaning |
| --- | --- |
| `schema` | Format version. Bumped only on a breaking change; `archive.py` refuses a version it does not know. |
| `status` | `open`, `active`, `blocked` or `done`. `blocked` means a member raised a question nobody has answered. |
| `epic` | An epic slug, or `null`. |
| `links` | Relations to other subjects, see below. |
| `descriptionDigest` | SHA-256 of the ticket description at the end of the last refinement. This is what tells Chrollo the ticket moved under him and the refinement is stale. |
| `steps` | One entry per step that has been reached. A step with no entry has not been reached. |

A step entry has `state` — `running`, `done`, `skipped` or `failed` — and, by state, `member`,
`at`, `file`, `reason` (why it was skipped) and `error` (why it failed).

Step identifiers and their order: `ticket` 10, `refine` 20, `design` 30, `dev` 40, `review` 50,
`test` 60, `ship` 70. The numbers are the file prefixes, and they leave room between steps.

## Links between subjects

```json
{ "type": "depends-on", "id": "personal-58" }
```

| Type | Meaning | Reciprocal |
| --- | --- | --- |
| `parent` | this subject is part of that one | `child` |
| `child` | that subject is part of this one | `parent` |
| `depends-on` | this one cannot ship before that one | `blocks` |
| `blocks` | that one cannot ship before this one | `depends-on` |
| `relates-to` | worth reading together | `relates-to` |
| `supersedes` | this one replaces that one | `superseded-by` |
| `superseded-by` | that one replaces this one | `supersedes` |

Links are written on both sides. `archive.py validate` reports a one-sided link, and
`archive.py reindex --fix-links` writes the missing half.

An epic is not a link. A subject belongs to at most one epic, and a `parent` link is for a
subject split in two — not for grouping a body of work, which is what epics are.

## `epics/<slug>.json`

```json
{
  "schema": 1,
  "slug": "attachments",
  "title": "Attachments, end to end",
  "status": "open",
  "subjects": ["personal-58", "personal-62"],
  "narrative": "attachments.md",
  "createdAt": "2026-11-10T08:00:00Z",
  "updatedAt": "2026-11-19T09:12:30Z"
}
```

`subjects` is ordered — it is the order the work is meant to happen in, not the order it was
added. `status` is `open`, `active` or `done`. `narrative` names an optional sibling `.md` file
where the epic's story is written in prose: why this body of work exists, what was decided
across its subjects, what is left.

The link between a subject and its epic is written on both sides, like any other link, and
`validate` checks it the same way.

## `journal.md`

Append-only, one block per event, newest at the bottom:

```markdown
## 2026-11-19T09:12:04Z — refine — pakunoda

Rewrote the description around what already exists in the uploader. Two decisions
settled with the owner: keep the existing route, no confirmation dialog.
```

The journal is for a human reading back. Nothing parses it, so there is no format to respect
beyond the heading line, which is `## <ISO 8601 UTC> — <step> — <member>`.

## `index.json`

```json
{
  "schema": 1,
  "generatedAt": "2026-11-19T09:12:31Z",
  "subjects": [
    {
      "id": "personal-62",
      "title": "Attachment panel",
      "status": "active",
      "epic": "attachments",
      "step": "dev",
      "stepIndex": 4,
      "stepTotal": 7,
      "updatedAt": "2026-11-19T09:12:30Z"
    }
  ],
  "epics": [
    { "slug": "attachments", "title": "Attachments, end to end", "status": "open", "subjects": 2 }
  ]
}
```

`step` is the furthest step reached, skipped steps included. Nothing else reads this file; it
exists for the mod and for `/brigade` to answer "where was I" without walking the tree.

## `current.json`

```json
{
  "schema": 1,
  "subjectId": "personal-62",
  "title": "Attachment panel",
  "step": "dev",
  "stepIndex": 4,
  "stepTotal": 7,
  "member": "illumi",
  "epic": "attachments",
  "startedAt": "2026-11-19T09:12:30Z",
  "updatedAt": "2026-11-19T09:12:30Z"
}
```

When no subject is being worked on, the file holds `{"schema": 1, "subjectId": null}`. Chrollo
writes it when he enters and leaves a step; the mod only reads it. A `current.json` left behind
by an interrupted run is stale, not corrupt: the mod shows it until the next run overwrites it.

## Tooling

`scripts/archive.py` is stdlib-only Python 3.

| Command | What it does |
| --- | --- |
| `validate` | Checks every `subject.json` and epic file against this document, reports one-sided links and unknown schema versions. Exit code 1 on any error. |
| `reindex [--fix-links]` | Rebuilds `index.json`. With `--fix-links`, writes the missing half of one-sided links. |
| `show [ID]` | Prints a subject, or the whole board when given no id. |
| `new --tracker T --key K --title X [--if-missing]` | Creates a subject and prints its id. |
| `set ID [--status --title --url --project --digest --epic]` | Changes a subject's fields. |
| `step ID --step S --state X [--member --file --reason --verdict]` | Records the outcome of a step. A `skipped` state without `--reason` is refused. |
| `journal ID --step S [--member M] --file F` | Appends a block to the subject's journal. |
| `current [--id ID --step S --member M] [--clear]` | Sets or clears what the mod shows above the prompt. |
| `link ID --type T --to OTHER` | Links two subjects, writing both sides. |
| `epic SLUG [--title X] [--add ID] [--status S]` | Creates an epic, or adds a subject to one. |
| `digest [--file F]` | Prints the `sha256:…` digest of a description. |

Every mutating command rebuilds `index.json` before it returns, so the derived pair is never
behind the source of truth by more than one command.

`scripts/migrate.py` imports an older per-ticket directory layout; see
[`docs/migration.md`](migration.md).


The archive path comes from `--archive`, else `BRIGADE_ARCHIVE`, else the `archive` key of the
configuration resolved as [`docs/configuration.md`](configuration.md) describes.
