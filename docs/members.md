# The contract between the orchestrator and the members

Members are subagents. They do not share the orchestrator's conversation, they cannot ask the
user anything, and they cannot see each other work. Everything that passes between them passes
through the subject's directory in the archive. That is a constraint worth stating plainly,
because every rule below follows from it.

## What a brief contains

Chrollo gives every member the same five things, and the member reads the rest from disk:

| | |
| --- | --- |
| Subject directory | the absolute path of `subjects/<id>/`. Everything known is in there. |
| Step | which step is being played, so a member that covers two knows which one. |
| Output file | the absolute path of the single file to write. |
| Language | from `owner.language`. Every user-facing word the member writes is in it. |
| Format | for a member that produces tracker text: `html`, `adf` or `markdown`. |

The brief never carries the ticket's text. The member reads it from the directory, so there is
one copy of it and no chance of the two drifting.

## What a member returns

One file, at the path it was given. Not two, not a file plus a side effect somewhere else. A
member that wants to say something to the next member says it in that file.

### The verdict line

Every member ends its file with exactly one HTML comment, on its own line:

| Member | Possible verdicts |
| --- | --- |
| Pakunoda | *(none — her output is a description, not a judgement)* |
| Hisoka | `approved`, `changes-requested`, `blocked` |
| Shalnark | `done`, `partial`, `blocked` |
| Machi | `approved`, `changes-requested`, `blocked` |
| Feitan | `passing`, `failing`, `blocked` |
| Nobunaga | `ready`, `blocked` |

```
<!-- verdict: changes-requested -->
```

Chrollo reads that line and nothing else to decide what happens next. It is a comment so that
the file stays readable as prose, and it is exact so that reading it is not interpretation.

A file with no verdict line, or with two, is a failed step: Chrollo retries the member once,
then records the step as `failed` and stops.

### The description markers

Pakunoda's output carries the ticket text itself, which Chrollo has to extract and publish:

```
<!-- description:start -->
…
<!-- description:end -->
```

When she is creating a ticket rather than refining one, the line immediately before the opening
marker is `# Title`.

Everything outside the markers is her note to the humans, and it is never published to the
tracker.

### Blocked

A member that cannot continue writes a `## Blocked` section holding its questions, and ends with
the `blocked` verdict. Chrollo puts those questions to the user, writes the answers into the
subject directory, and runs the member again. The member never asks anybody anything itself,
because there is nobody on the other end of a subagent.

## What no member does

- **Talk to the tracker.** Chrollo does every read and write. A member that needs the ticket
  reads the copy on disk.
- **Commit, push, or open a pull request.** Nobunaga writes the texts; the user runs the
  gestures.
- **Move a card.** See `transitions` in the configuration.
- **Write outside its output file**, except Shalnark and Feitan, who write code and tests — that
  is the work.
- **Ask the user a question.**

## Why each member exists

A step is a member rather than another paragraph in the orchestrator when it needs either a
different posture or a clean context:

- **Pakunoda** needs to read a lot of code and keep only a page of it.
- **Hisoka** has to look at the interface without being told what it was meant to be.
- **Shalnark** needs the whole context of the project and none of the review's.
- **Machi** must read the diff without having written it. This is the one that would be worth
  nothing done by the author.
- **Feitan** must try to break what Shalnark just convinced himself was right.
- **Nobunaga** needs everything, and produces three paragraphs.
