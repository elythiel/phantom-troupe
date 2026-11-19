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
| **Kalluto** | UX, interface, accessibility — only when there is something to look at |
| **Illumi** | implementation |
| **Machi** | code review |
| **Feitan** | tests and edge cases |
| **Nobunaga** | shipping: commit message, pull request, version |
| **Shizuku** | the archive itself — the journal, the index, the epics. Not an agent: she is `scripts/archive.py` |

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

## What this plugin can do on your machine

Read this before installing. A plugin runs with your permissions, so the honest answer is more
useful than a reassuring one.

**The members are subagents, and two of them write.** That is the job, not a side effect:

| Member | Tools |
| --- | --- |
| Illumi, Feitan | `Read`, `Edit`, `Write`, `Bash`, `Grep`, `Glob` — they write code and tests, and run your project's commands |
| Pakunoda, Machi, Nobunaga | `Read`, `Grep`, `Glob`, `Bash`, `Write` — they read your code and run read-only commands |
| Kalluto | `Read`, `Grep`, `Glob`, `Write` — no shell at all |

Everything they run still goes through Claude Code's own permission prompts. This plugin asks for
no exemption from them.

**The mod only reads.** You do not have to take that on trust — `claude plugin validate` works it
out from the code and prints the list:

```
calls: $.clock.every, $.command.register, $.env.get, $.fs.exists,
       $.fs.read, $.ui.invalidate, $.ui.resolve
env writes: nothing
```

No process, no network, no write.

**The only network traffic goes to the tracker you configured**, from `scripts/tracker.py`, to the
`baseUrl` in your own configuration. A Jira tracker goes through your session's Atlassian
connector instead, so this plugin makes no request of its own for it. The scripts are stdlib-only
Python with no third-party dependency, and contain no `eval`, no `exec` and no subprocess call.

**Your token is read at the moment of the call**, from the file your configuration names, placed
in an `Authorization` header, and never printed, logged or written to the archive. Error messages
give the method and the path, not the host.

**What the troupe will never do**: commit, push, open a pull request, or run a release command.
Nobunaga writes those texts; you run the gestures. It moves a card only where `transitions`
allows, and `null` there means you move it yourself.

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
🕷 personal-62  Attachment panel  · step 4/7 implementation — illumi  · epic attachments
```

`/brigade-board` prints the whole archive, and `/brigade-epic <slug>` one epic. Both are
display-only: what they print is for you and never enters the conversation. See
[`docs/mod.md`](docs/mod.md).

## Documentation

| | |
| --- | --- |
| [`docs/configuration.md`](docs/configuration.md) | Every configuration key, and where the file goes |
| [`docs/archive.md`](docs/archive.md) | The archive format, and the tool that checks it |
| [`docs/members.md`](docs/members.md) | The contract between the orchestrator and the members |
| [`docs/mod.md`](docs/mod.md) | What the mod draws, and what it is allowed to do |
| [`docs/i18n.md`](docs/i18n.md) | Adding a language |
| [`docs/migration.md`](docs/migration.md) | Importing an older per-ticket directory layout |

## Commands

| | |
| --- | --- |
| `/brigade [key or intent]` | Run the troupe on a subject |
| `/brigade status` | The board |
| `/brigade-doctor` | Check the installation and say what to fix |
| `/brigade-board` | The board, printed by the mod, never sent to Claude |
| `/brigade-epic <slug>` | One epic and the subjects in it |

## Languages

The repository is in English; the troupe writes in whatever `owner.language` says. Adding a
language means one JSON file in `locales/` — see [`docs/i18n.md`](docs/i18n.md).

## License

MIT — see [LICENSE](LICENSE).
