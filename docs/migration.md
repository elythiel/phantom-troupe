# Importing an older layout

`scripts/migrate.py` imports a directory that holds one subdirectory per ticket, each full of
Markdown files named after whoever wrote them. That is what most hand-rolled agent setups leave
behind, and it maps cleanly onto the archive's steps.

It **copies**: nothing is moved or deleted from the source. It changes nothing at all until you
pass `--apply`.

```sh
# See what would happen
scripts/migrate.py --source ~/old-team --tracker work --project my-project

# Do it
scripts/migrate.py --source ~/old-team --tracker work --project my-project --apply
scripts/archive.py reindex
```

| Flag | Role |
| --- | --- |
| `--source` | The directory holding one subdirectory per ticket. Each subdirectory's name becomes the ticket key. |
| `--tracker` | The tracker name to file the subjects under, as spelled in your configuration. The subject id is `<tracker>-<key>`. |
| `--project` | Project alias recorded on each subject. Optional. |
| `--match` | A regular expression; only matching directory names are imported. Default: everything. |
| `--map` | A JSON file overriding the file-name mapping. |
| `--archive` | Target archive. Defaults to the configured one. |
| `--apply` | Write. Without it, the script only prints its plan. |

## The default mapping

File names are matched without their extension, lowercased.

| Source file | Becomes |
| --- | --- |
| `story`, `ticket` | `steps/10-ticket.md` |
| `po-review`, `requirements`, `refine` | `steps/20-refine.md` |
| `ux-review`, `design` | `steps/30-design.md` |
| `dev-challenge`, `mr-description`, `implementation` | `steps/40-dev.md` |
| `code-review`, `review` | `steps/50-review.md` |
| `test-report`, `tests` | `steps/60-test.md` |
| `ship`, `release` | `steps/70-ship.md` |
| `summary` | appended to `journal.md` |
| `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.svg`, `.pdf` | `attachments/` |
| anything else | left behind, and listed in the plan |

To change it, pass a JSON file of the same shape to `--map`; your entries are merged over the
defaults.

```json
{ "analysis": "refine", "qa": "test" }
```

## What the imported subject looks like

Every imported subject is written with `status: "done"` and each imported step marked `done`.
The import cannot know what really happened, so it records what it found and nothing more:
there is no `url`, no `descriptionDigest`, no epic and no links. `importedFrom` marks it as an
import.

The practical consequence is that an imported subject is **history, not work in progress**.
Running `/troupe` on one will consider every step already played. If you want to carry on with
an imported subject, clear the steps you want replayed from its `subject.json` first.

A subject whose directory already exists in the archive is skipped, so running the import twice
is safe.
