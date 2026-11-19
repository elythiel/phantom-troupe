---
description: Check that the Phantom Troupe is correctly installed - configuration, archive, trackers - and say precisely what to fix.
argument-hint: "[--tracker=name]"
---

Check this installation and report. **Change nothing**: no file is written, no card is moved, no
ticket is touched. Arguments: `$ARGUMENTS`

Run through the list in order and print one line per check, each either passing or carrying the
exact thing to do about it. Keep going after a failure — a first missing piece usually explains
several of the lines below it, and the user wants the whole picture in one pass.

## 1. Configuration

- Which of the three locations the configuration was found in, or that none exists — in which
  case say which file to create from `config.example.json`, and stop there: everything below
  depends on it.
- `archive` is set and its parent directory is writable.
- `owner.language` is set. If it is missing, say that the troupe will fall back to English.
- At least one tracker is declared, and `defaultTracker` names one of them.

## 2. Each tracker

For every tracker, or only the one `--tracker` names:

- `kind` is `vikunja` or `jira-mcp`.
- `keyPattern` is a valid regular expression, and no two trackers' patterns match the same
  example key. Overlapping patterns are not an error, but they mean a key will have to be
  disambiguated by hand every time, so say so.
- `states` declares `doing` at minimum, and every state named in `transitions` has labels.
- **`vikunja`**: the token file exists and is readable, and its permissions are not wider than
  `600` — say so if they are. Then run
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tracker.py" --tracker <name> states --project <alias>`
  and report which configured states matched a real column and which did not. A state with no
  column is the failure that only shows up when a card refuses to move.
- **`jira-mcp`**: the Atlassian MCP tools are in your tool list, the cloud id resolves, and
  `projectKeys` is not empty.

**Never print the token, not even partially.** Report that the file is readable, nothing more.

## 3. Archive

- `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/archive.py" validate` — report its output as it comes.
- How many subjects and epics there are, and the most recently updated subject.
- Whether `current.json` points at a subject that is still being worked on. A stale one is not an
  error; say it is stale and that the next run will overwrite it.

## 4. Plugin

- Claude Code's version, and whether it is at least 2.1.287. Below that the mod does not load and
  the strip above the prompt and `/troupe-board` are simply absent — the rest works.
- Whether the six members are in your agent list, and under what name.

## Report

End with one sentence: ready, or the single most important thing to fix first. If several things
are broken, order them by what unblocks the most.
