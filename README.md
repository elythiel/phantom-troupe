# Fantôme Troupe

A team of Claude Code agents that carries a development subject from end to end — ticket
creation, refinement, design, implementation, review, testing, shipping — **playing only the
steps that are actually needed**.

It remembers what it did, and it knows how to link subjects together into epics.

> Status: under construction. Nothing is usable yet.

## How it is built

Five layers, with a strict separation between them:

| Layer | Form | Role |
| --- | --- | --- |
| Orchestration | the `/brigade` command | decides the route, calls the members, asks the questions |
| Members | subagents | do the work, in isolated context, and write to the archive |
| Tracker | a skill | hides Vikunja and Jira behind one vocabulary |
| Archive | local files | the state, the history, the epics |
| Interface | a mod | **reads** the archive and displays it. It drives nothing |

That last line is the structural decision: the command writes the state, the mod shows it. No
logic is duplicated in JavaScript, and everything keeps working with the mod disabled.

## The troupe

| Member | Role |
| --- | --- |
| **Chrollo** | the orchestrator — he does nothing himself, he summons |
| **Pakunoda** | ticket creation and refinement: she digs out of the code what the ticket does not say |
| **Hisoka** | UX, interface, accessibility — only when there is something to look at |
| **Shalnark** | implementation |
| **Machi** | code review |
| **Feitan** | tests and edge cases |
| **Nobunaga** | shipping: commit message, pull request, version |
| **Shizuku** | the archive: the journal, the index, the epics |

## The steps, and when they run

Chrollo assesses the subject, announces the route **with a reason for every step he skips**,
waits for your approval, then runs through without coming back to you — except for a decision
that materially changes the work.

| Step | Runs when | Skipped when |
| --- | --- | --- |
| Ticket | the input is an intent, not a ticket key | a key was given |
| Refinement | no acceptance criteria, or the description changed since the last refinement | refinement is current |
| Design | mockups are attached, or the scope touches the interface | the subject has no visible surface |
| Implementation | no matching work exists yet | a coherent diff is already there |
| Review | a diff exists and the review is missing or stale | the review is current |
| Tests | the project has a suite and the diff touches logic | nothing to verify |
| Shipping | the review passed and nothing is delivered yet | already delivered |

Every step can be forced or disabled from the configuration, and a route is resumable: running
`/brigade` again on a subject picks up where the archive left off.

## Requirements

- Claude Code **2.1.287 or newer** — mods do not exist before that.
- A tracker: a [Vikunja](https://vikunja.io) instance, or a Jira Cloud reached through the
  Atlassian MCP connector.

## Install

```sh
git clone https://github.com/elythiel/fantome-troupe.git
```

To iterate on the plugin without installing it:

```sh
claude --plugin-dir /path/to/fantome-troupe
```

To keep it, add the directory as a local marketplace, then install the plugin from `/plugin`.

## Configuration

This repository holds no host, no project key, no token and nobody's name. All of that lives in
a file that is never committed:

```sh
mkdir -p ~/.config/fantome-troupe
cp config.example.json ~/.config/fantome-troupe/config.json
```

Every key is documented in [`docs/configuration.md`](docs/configuration.md).

## What it looks like

While a subject is being worked on, the mod keeps one row above the prompt:

```
🕷 personal-62  Attachment panel  · step 4/7 implementation — shalnark  · epic attachments
```

`/brigade-board` prints the whole archive, and `/brigade-epic <slug>` one epic. Both are
display-only: what they print is for you and never enters the conversation. See
[`docs/mod.md`](docs/mod.md).

## Languages

The repository is in English; the troupe writes in whatever `owner.language` says. Adding a
language means one JSON file in `locales/` — see [`docs/i18n.md`](docs/i18n.md).

## License

MIT — see [LICENSE](LICENSE).
