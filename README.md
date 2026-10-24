# Stash

Fuzzy keyword search over a plain-text stash you own, as an Alfred workflow.

- **Search** with any words, in any order, any subset of them, any part of a word: `st stg k8` finds *Kube switch to staging*.
- **Add** by typing: whatever you searched for is always offered as a new entry, so a miss is one ↩ away from being stored.
- **Own the data**: one line per entry in a text file you can edit, grep, sync and keep in git. A line is searchable in full until you add a `|` to split what you search by from what you copy.
- **Fast**: no dependencies, built to stay well under Alfred's "instant" threshold for a stash of a few thousand entries.

```
st stg k8
┌──────────────────────────────────────────────────────┐
│ Kube switch to staging                               │
│ kubectl config use-context staging                   │
├──────────────────────────────────────────────────────┤
│ Add: stg k8                                          │
│ stg k8  →  stg k8   (keywords | title | payload)     │
└──────────────────────────────────────────────────────┘
  ↩ copy (or add)   ⇧↩ paste   ⌘↩ edit   ⌥↩ delete   ⌃ keywords
```

## Contents

- [Install](#install)
- [Quick start](#quick-start)
- [The stash file](#the-stash-file)
- [Searching](#searching)
- [Actions on a result](#actions-on-a-result)
- [Adding entries](#adding-entries)
- [Editing and deleting](#editing-and-deleting)
- [Configuration](#configuration)
- [Recipes](#recipes)
- [Performance](#performance)
- [Limitations](#limitations)
- [Development](#development)

## Install

Requirements: Alfred 5 with the Powerpack, and Python 3.9 or newer. There are no packages to install.

1. Double-click `Stash.alfredworkflow` and press **Import**.
2. Python: the default is `/usr/bin/python3`, which macOS provides once the Xcode Command Line Tools are installed (`xcode-select --install`). To use another interpreter, set the `python` variable to its **absolute path**, for example `/opt/homebrew/bin/python3` or the output of `uv python find 3.12`.
3. Optionally point `db_file` at an existing file and set `editor` (see [Configuration](#configuration)).

## Quick start

`st`, `sta` and `stash` are the same keyword; use whichever your fingers produce.

```
st ssh prod web | Prod web box | ssh deploy@10.0.1.5     ↩ adds the entry
st prod                                                  ↩ copies ssh deploy@10.0.1.5
st                                                       browse everything; ⌘↩ opens the file
```

To explore with sample data first, set `db_file` to the `examples/stash.txt` that ships with the source.

## The stash file

Default location: `~/.config/stash/stash.txt`, created on the first add. One entry per line, and one rule:

**A line is searchable in full, and copied in full, until you put a `|` in it.** Then the words *before* the first `|` are what you search by, and what comes after is what you see and copy, never searched.

```
pihole update finished                                   every word searchable; copies itself
ssh prod web | ssh deploy@10.0.1.5                       search by ssh/prod/web; copies the command
ssh prod web | Prod web box | ssh deploy@10.0.1.5        same, shown as "Prod web box" (its words are searchable too)
```

Use plain lines for notes, facts, anything short enough to read in the results. Add a `|` when the thing you want copied is long, cryptic or a URL, so its innards don't pollute search; add a second `|` when you also want a readable title.

In full, a line is `keywords | title | payload`:

| Field | Meaning |
|---|---|
| keywords | Words to search by, separated by spaces or commas. The only required field. |
| title | What Alfred shows as the result. Optional, defaults to the keywords. Its words are searchable too. |
| payload | What ↩ copies. Optional, defaults to the keywords. **Never searched.** May contain `\|`. |

Rules:

- Only the first two `|` split fields, so the payload can hold shell pipes.
- With two fields the second one is the **payload**: `wifi guest | GuestNetwork-5G`.
- To skip the title but keep a piped payload, leave the title empty: `uuid gen || uuidgen | tr A-Z a-z`.
- Lines starting with `#` and blank lines are ignored, so comment and group freely.
- Whitespace around fields is ignored, so you can align columns.
- The file is UTF-8; keywords in any script work (`кава coffee`). A stray non-UTF-8 byte won't break search, and add or delete keep such bytes exactly as they were.

A sample of what a real file can look like (the full one is in `examples/stash.txt`):

```
# shell commands
ssh prod web          | Prod web box              | ssh deploy@10.0.1.5
k8s ctx staging       | Kube switch to staging    | kubectl config use-context staging
k8s pods failing      | Kube failing pods         | kubectl get pods -A --field-selector=status.phase!=Running
port listen who       | Who listens on port 8080  | lsof -nP -iTCP:8080 -sTCP:LISTEN | grep -v COMMAND
uuid gen              ||                            uuidgen | tr A-Z a-z

# links
grafana api latency   | API latency dashboard     | https://grafana.example.com/d/api-latency

# text snippets
email work            | Work email                | name.surname@example.com
reply thanks review   | Thanks for the review     | Thanks for the review! I've addressed the comments, PTAL.

# plain lines: searchable in full, copied in full
pihole update finished
deploy checklist
wifi guest            | GuestNetwork-5G
```

## Searching

Type `st` (or `sta`, or `stash`) followed by any words. Each query word must match **some** keyword or title word of an entry; the order of query words doesn't matter, and entries may have more words than you typed.

A query word matches a stash word in one of four ways, strongest first:

| Query word | Stash word | Match | Score |
|---|---|---|---|
| `prod` | prod | whole word | 4 |
| `pro` | prod | start of word | 3 |
| `rod` | prod | inside word | 2 |
| `prd`, `stg` | prod, staging | letters in order, inside one word | 1 |

Scores of all query words add up. Equal scores go to the entry with fewer words (the tighter match), then to the one higher in the file. Alfred also learns which results you pick and moves them up over time.

The last result is always **Add: …** for what you typed (see [Adding entries](#adding-entries)); it is left out of the examples below.

| You type | You get | Why |
|---|---|---|
| `st` | every entry, in file order | empty query browses the file |
| `st prod` | Prod web box, Kube switch to prod | whole-word match in keywords |
| `st web ssh` | Prod web box, Staging web box | any order; Prod is first in the file |
| `st stg` | Staging web box, Kube switch to staging | letters in order inside *staging* |
| `st k8 prd` | Kube switch to prod | `k8` starts *k8s*, `prd` is inside *prod* |
| `st ctx` | Kube switch to prod, Kube switch to staging | same score; the prod entry has fewer words |
| `st lat` | API latency dashboard | `lat` starts *latency* |
| `st grf lat` | API latency dashboard | `grf` is inside *grafana* |
| `st thnk rev` | Thanks for the review | title words are searchable too |
| `st кав` | Кава ☕ | Unicode works |
| `st finished` | pihole update finished | a plain line is searchable in full |
| `st deploy` | deploy checklist | the ssh entries' payloads mention *deploy*, but text after a `\|` isn't searched |
| `st ssh prod staging` | only *Add* | every query word must match |
| `st kctx` | only *Add* | letters-in-order stays inside one word; type `st k ctx` |
| `st stgaing` | only *Add* | swapped letters aren't tolerated, dropped letters are |

Press ⇥ (Tab) on a result to put its keywords into the query.

## Actions on a result

| Keys | Action |
|---|---|
| ↩ | Copy the payload to the clipboard (on the *Add* item: store the entry) |
| ⇧↩ | Copy and paste the payload into the frontmost app |
| ⌘↩ | Open the stash in your editor at this entry's line (on *Add* or a hint: at the top) |
| ⌥↩ | Delete this entry from the file |
| ⌃ (hold) | Show the entry's keywords in the subtitle |
| ⌘C | Copy the payload (Alfred's own copy shortcut) |
| ⌘L | Show the payload in Large Type |

The payload is copied literally: Alfred placeholders such as `{date}` inside it are not expanded.

## Adding entries

There is no separate add keyword. Whatever you type after `st` is offered as a new entry in the **Add: …** result, whose subtitle previews exactly what will be stored. Press ↩ on it and the line is appended to the file, confirmed by a notification.

- With no matches, *Add* is the only result, so a miss is ↩ away from being stored under the words you just searched for.
- With matches, *Add* is the last result: ↓ to it, or keep typing.
- As soon as you type a `|`, you are clearly writing an entry, so *Add* becomes the **first** result and ↩ stores it. The words before the `|` are still searched, so you see at once whether such an entry already exists.

| You type after `st` | Stored line | Shown as | Copies |
|---|---|---|---|
| `ssh prod web \| Prod web box \| ssh deploy@10.0.1.5` | same | Prod web box | `ssh deploy@10.0.1.5` |
| `wifi guest \| GuestNetwork-5G` | same | wifi guest | `GuestNetwork-5G` |
| `logs api \| Tail API logs \| kubectl logs -f deploy/api \| grep ERROR` | same | Tail API logs | `kubectl logs -f deploy/api \| grep ERROR` |
| `uuid gen \|\| uuidgen \| tr A-Z a-z` | same | uuid gen | `uuidgen \| tr A-Z a-z` |
| `deploy checklist` | same | deploy checklist | `deploy checklist` |

Entries are appended at the end of the file. Reorder or group them later in your editor; the file is the source of truth.

## Editing and deleting

- ⌘↩ on any result opens the file in your editor at that entry's line (with an editor that supports lines, see below); on the *Add* item or on a hint it opens at the top.
- ⌥↩ on a search result deletes that line. Deletion matches the line's content, so if you edited the file since the search, it reports *entry not found* instead of deleting the wrong line. Comments and other lines are kept as they are, and a stash that is a symlink (to iCloud, Dropbox, a git repo) stays a symlink.

## Configuration

Set these in Alfred: open the workflow and click the **[𝑥]** button.

| Variable | Default | Meaning |
|---|---|---|
| `db_file` | `~/.config/stash/stash.txt` | The stash file. `~` is expanded. |
| `editor` | `open -t {file}` | Command used by ⌘↩. `{file}` and `{line}` are filled in. |
| `max_results` | `50` | How many results Alfred receives. |
| `python` | `/usr/bin/python3` | Interpreter, 3.9 or newer. Absolute path, no `~`. |

Alfred runs workflows with a minimal `PATH`, so use the full path of your editor's command line tool. Quote paths with spaces:

| Editor | `editor` value |
|---|---|
| Default text editor | `open -t {file}` |
| VS Code | `'/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code' -g {file}:{line}` |
| Sublime Text | `'/Applications/Sublime Text.app/Contents/SharedSupport/bin/subl' {file}:{line}` |
| Zed | `/usr/local/bin/zed {file}:{line}` |
| BBEdit | `/usr/local/bin/bbedit +{line} {file}` |
| Neovim in WezTerm | `/Applications/WezTerm.app/Contents/MacOS/wezterm start -- /opt/homebrew/bin/nvim +{line} {file}` |

If the editor can't be found, a notification tells you so.

## Recipes

### Several stashes

Select every object of the workflow in Alfred, copy and paste it, give the copied Script Filters their own keywords such as `li` and `links`, and start each copied script with an export:

```bash
export db_file=~/notes/links.txt; exec "${python:-/usr/bin/python3}" -S -X utf8 run.py search "$1"
```

Every script of the copy needs the same export (search, add, delete, edit), because Alfred does not pass a script's environment on to the objects it is connected to.

### Sync and history

Keep the file wherever you like and point `db_file` at it, or symlink it:

```bash
mkdir -p ~/.config/stash
ln -s ~/Library/Mobile\ Documents/com~apple~CloudDocs/stash/stash.txt ~/.config/stash/stash.txt
```

Since it's plain text, `git init` in its folder gives you history and diffs for free.

### Use it from the terminal

In Alfred, right-click the workflow and choose **Open in Finder** to find its folder, then link it somewhere short (same command in bash and fish):

```bash
ln -s "$HOME/Library/Application Support/Alfred/Alfred.alfredpreferences/workflows/user.workflow.XXXX" ~/.stash
```

Search and copy the best match, in bash or fish (needs `jq`):

```bash
python3 ~/.stash/run.py search k8s prod | jq -r '.items[0].arg' | pbcopy
```

Add an entry:

```bash
python3 ~/.stash/run.py add 'logs api | Tail API logs | kubectl logs -f deploy/api'
```

Save the command you just ran under some keywords, so the next time it's one `st` away.

fish, in `~/.config/fish/functions/stash.fish`:

```fish
function stash --description 'Save the previous command to the stash under the given keywords'
    python3 ~/.stash/run.py add "$argv || $history[1]"
end
```

bash, in `~/.bashrc` (`-2` because the `stash` line itself is already the latest history entry):

```bash
stash() { python3 ~/.stash/run.py add "$* || $(fc -ln -2 -2 | sed 's/^[[:space:]]*//')"; }
```

```
$ kubectl get pods -A | grep -v Running
$ stash k8s pods broken
Added: k8s pods broken
```

The `||` keeps pipes in the saved command intact.

## Performance

Alfred starts a new process on every keystroke, so the whole run counts, not just the search. Medians per keystroke, measured on a Linux cloud VM with Python 3.9 (an Apple Silicon Mac is typically faster):

| Entries | Per keystroke |
|---|---|
| 1,000 | ~35–45 ms |
| 3,000 | ~50–60 ms |
| 10,000 | ~120 ms |

About 25 ms of that is starting Python and importing modules, which no pure-Python workflow avoids; the rest is reading and parsing the file (~6 ms per 1,000 lines) and matching (~1.5 ms per 1,000 lines). Reproduce with `uv run python bench.py --python /usr/bin/python3`; add `--stress` for a vocabulary where most queries match most entries.

The design is deliberately the simple one: the file is parsed on every keystroke and there is no cache or index. That stays instant for the few hundred to few thousand entries a personal stash has. An earlier version cached the searchable text keyed by file checksum and scanned it with hand-tuned string checks, which held 10,000 entries at ~50 ms and 50,000 at ~100 ms, at the cost of an extra module and a cache directory; it is in the git history (tag `v1.0-cached`) if you ever need it.

What keeps it fast:

- Each query word compiles to one regex whose alternatives are ordered from whole word to in-word letters, so a single `match` returns both whether and how well the word matches, and the in-word pattern never backtracks.
- Python runs with `-S` (no `site` import) and the code avoids heavy modules: `dataclasses` alone costs ~12 ms and `pathlib` ~9 ms per start, so `NamedTuple`, `os.path` and `os.execvp` take their place.
- Alfred is set to run the script immediately and to cancel a still-running search when you type the next letter.

## Limitations

- Swapped letters (`stgaing`) don't match; dropped letters (`stgng`) do.
- Letters-in-order matching stays within one word: `kctx` won't find `k8s ctx`, `k ctx` will.
- Title words are split on whitespace only, so in a title like *Kube: switch*, `kube` matches as the start of `kube:` rather than a whole word.
- Payloads are single lines.
- It's a plain-text file: don't store secrets you wouldn't keep in a dotfile.

## Development

```bash
uv sync
uv run pytest                                       # 160 tests
uv run --python 3.9 --isolated --with pytest --with pytest-mock pytest   # what /usr/bin/python3 is on macOS
uv run python bench.py                              # latency per keystroke
uv run python make_plist.py                         # regenerate info.plist after changing keywords or wiring
```

Build the installable workflow (same in bash and fish):

```bash
zip -r dist/Stash.alfredworkflow info.plist icon.png run.py stash -x '*__pycache__*'
```

| Path | Responsibility |
|---|---|
| `stash/entries.py` | Parse a line into an `Entry` with its searchable text |
| `stash/matching.py` | One regex per query word, scoring, ranking |
| `stash/store.py` | Load entries, append, delete lines; atomic, symlink-safe writes |
| `stash/alfred.py` | Alfred Script Filter JSON: results, the *Add* item, hints |
| `stash/cli.py` | Commands `search`, `add`, `delete`, `edit`; workflow variables |
| `run.py` | Entry point Alfred calls |
| `make_plist.py` | Source of `info.plist`: keywords, objects, connections, variables |
| `tests/` | pytest suite, including a structural check of `info.plist` |
| `bench.py` | End-to-end latency benchmark |
| `examples/stash.txt` | Sample stash |
