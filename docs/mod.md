# The mod

The mod draws two things, and reads to do it. It never writes, never runs a process and never
reaches the network — `claude plugin validate` prints the list of calls a mod makes, and for this
one it is `$.fs.read`, `$.fs.exists`, `$.env.get`, `$.ui.resolve`, `$.ui.invalidate`,
`$.command.register` and `$.clock.every`. Nothing else. You can check that yourself before
trusting it:

```sh
claude plugin validate /path/to/fantome-troupe
```

That is a deliberate boundary. `/brigade` owns the archive; the mod is a window onto it. A reader
cannot corrupt what it reads, and everything keeps working with mods turned off — you simply lose
the window.

## The row above the prompt

While a subject is being worked on, one row sits above the prompt:

```
🕷 personal-62  Attachment panel  · step 4/7 implementation — illumi  · epic attachments
```

It comes from `current.json`, which `/brigade` writes when it enters a step and clears when it
finishes. No subject in progress means no row at all — the mod draws nothing rather than drawing
"nothing to show".

The row refreshes at the end of every turn and every ten seconds, and only redraws when the file
actually changed.

A row left over from an interrupted run is stale, not wrong. The next run overwrites it; to clear
it by hand, `scripts/archive.py current --clear`.

## `/brigade-board`

Prints the whole archive: every subject with its status, the step it reached, its epic and its
title, then the epics with how many subjects each holds.

**What it prints is for you, not for Claude.** It is marked display-only, so it never enters the
conversation and costs no context. That is the point of having it in the mod rather than as a
command Claude answers: asking "where am I" should cost nothing.

## `/brigade-epic [slug]`

With a slug, one epic and the subjects in it, in the order the epic lists them. Without one, the
epics you have. Display-only in the same way.

## Languages

Everything the mod prints goes through `locales/`, selected by `owner.language`. See
[`docs/i18n.md`](i18n.md).

## When the mod shows nothing

| What you see | Why |
| --- | --- |
| No row, ever | Nothing is in progress — or Claude Code is older than 2.1.287 and the mod never loaded. `/plugin` lists the mods a session loaded. |
| The board says the archive is empty | The configured `archive` does not exist yet, or holds no subject. `/brigade-doctor` says which. |
| A row naming a subject you finished | A stale `current.json`. Harmless; see above. |
| `/brigade-board` is not in the command list | Another plugin already registered that name, or the mod failed to load. |

The mod never stops a session from starting and never breaks a turn: every one of its handlers
swallows its own errors and falls back to drawing nothing. A mod that can take the session down
with it is not worth a status line.
