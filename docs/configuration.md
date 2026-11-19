# Configuration

This repository holds **no host, no project key, no token and nobody's name**. Everything that
identifies you lives in a configuration file that is never committed. The repository ships only
`config.example.json` and this document.

## Where the troupe looks for its configuration

In this order, first one found wins:

1. the path in the `BRIGADE_CONFIG` environment variable;
2. `.brigade/config.json` at the root of the current project — add `.brigade/` to that project's
   `.gitignore`;
3. `~/.config/fantome-troupe/config.json` — your personal configuration, valid everywhere.

If none exists, the troupe stops and tells you what to create. It never guesses a host or a
project identifier.

To start:

```sh
mkdir -p ~/.config/fantome-troupe
cp config.example.json ~/.config/fantome-troupe/config.json
$EDITOR ~/.config/fantome-troupe/config.json
```

## Keys

### `archive` — string

The directory where the troupe's memory lives: subjects, their per-step deliverables, the
journal and the epics. A leading `~` is expanded. This directory holds your real work; do not
put it in a public repository.

Default: `~/.local/share/fantome-troupe`.

### `owner` — object

| Key | Role |
| --- | --- |
| `name` | The name the members use to address you. Injected at briefing time; no agent hardcodes it. |
| `language` | The language the troupe writes in: a BCP 47 tag such as `fr`, `en` or `pt-BR`. See [`docs/i18n.md`](i18n.md). |

### `defaultTracker` — string

The tracker used when nothing else decides. It is a key of `trackers`.

### `trackers` — object

Each entry is a tracker, named however you like (`personal`, `work`, `client-x`). That name only
means something to you: it is what you pass to `--tracker=`.

| Key | Required | Role |
| --- | --- | --- |
| `kind` | yes | The adapter: `vikunja` or `jira-mcp`. The adapter is the only thing the repository knows; everything else comes from here. |
| `keyPattern` | yes | A regular expression that recognizes a ticket key of this tracker. Used to infer the tracker from the argument to `/brigade`. Two trackers with overlapping patterns force a question. |
| `states` | yes | Your own labels for the four states the troupe distinguishes: `todo`, `doing`, `review`, `done`. Each state accepts several labels; matching ignores case. |
| `transitions` | yes | What the troupe is **allowed** to move. See below. |
| `descriptionFormat` | yes | How to write a description: `html` (Vikunja), `adf` (Jira Cloud) or `markdown`. |
| `comments` | no | `postDevNote` and `postReviewNote`: whether a step note is posted as a ticket comment. |

#### Keys specific to `kind: "vikunja"`

| Key | Role |
| --- | --- |
| `baseUrl` | API root, up to and including `/api/v1`. |
| `tokenFile` | Path to a file holding the token and nothing else, sent as `Authorization: Bearer`. Keep it `chmod 600`. The token is never written to the archive nor printed. |
| `projects` | Readable alias → numeric project id. |
| `defaultProject` | The alias used when no project is given. |

#### Keys specific to `kind: "jira-mcp"`

This adapter goes through your session's Atlassian MCP connector, so there is no URL and no
token to write here.

| Key | Role |
| --- | --- |
| `projectKeys` | The project keys the troupe may touch. It refuses a ticket from any other project. |
| `cloudId` | `auto` to let the connector resolve it, or a fixed value. |

#### `transitions` — who moves the card

Each key is either a state name (`todo`, `doing`, `review`, `done`) or `null`. `null` means
**the troupe does not move the card at that moment** — you do.

| Key | When |
| --- | --- |
| `start` | Implementation begins. |
| `review` | The review is delivered. |
| `finish` | The shipping texts are written. |

The careful setting, and the one in the example, is
`{"start": "doing", "review": null, "finish": null}`: the troupe announces that it has picked the
subject up, and nothing else moves without you.

### `steps` — object

For each of the seven steps (`ticket`, `refine`, `design`, `dev`, `review`, `test`, `ship`):

| Value | Effect |
| --- | --- |
| `auto` | Chrollo decides whether the step is needed, and says why when he skips it. This is the normal mode. |
| `always` | The step always runs. |
| `never` | The step never runs. |

### `members` — object, optional

Overrides per member. The key is the member's lowercase name; today the only option is `model`.

```json
"members": {
  "illumi": { "model": "opus" },
  "feitan": { "model": "sonnet" }
}
```

An unset member keeps the model declared in its own agent file. Chrollo always runs in the main
session, so he has no entry here.

### `workspaces` — object, optional

Binds a local directory to a tracker and a project, so you do not need a `.brigade/config.json`
in every repository. The key is a path; the longest key that prefixes the current directory wins.

```json
"workspaces": {
  "~/code/my-project": { "tracker": "personal", "project": "my-project" }
}
```

## What must never be committed

The repository's `.gitignore` already excludes `config.json`, `*.local.json`, `.brigade/`,
`*.token` and `token`. If you put a configuration file anywhere else, exclude it too. The rule
fits in one sentence: **the repository describes mechanisms, the configuration describes your
installation.**
