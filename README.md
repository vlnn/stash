# Stash

Fuzzy keyword search over a plain-text stash you own, as an Alfred workflow.

- **Search** with any words, in any order, any subset of them, any part of a word: `st stg k8` finds `k8s ctx staging kube`.
- **Act**: ↩ copies the payload, or opens it when it is a URL, a path or an Alfred flow; ⇧↩ pastes it.
- **Add** by typing: whatever you searched for is always offered as a new entry, so a miss is one ↩ away from being stored.
- **Own the data**: one line per entry in a text file you can edit, grep, sync and keep in git. The format is one rule: everything after the first `|` is the payload.
- **Fast**: no dependencies, built to stay well under Alfred's "instant" threshold for a stash of a few thousand entries.

```
st stg k8
┌──────────────────────────────────────────────────────┐
│ k8s ctx staging kube                                 │
│ kubectl config use-context staging                   │
├──────────────────────────────────────────────────────┤
│ Add: stg k8                                          │
│ stg k8   (words | payload)                           │
└──────────────────────────────────────────────────────┘
  ↩ copy / open / add   ⇧↩ paste   ⌘↩ edit   ⌥↩ delete
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
st ssh prod web | ssh deploy@10.0.1.5     ↩ adds the entry
st prod                                   ↩ copies ssh deploy@10.0.1.5
st http://127.0.0.1:4000                  ↩ adds it; next time, st 4000 ↩ opens it
st                                        browse everything; ⌘↩ opens the file
```

To explore with sample data first, set `db_file` to the `examples/stash.txt` that ships with the source.

## The stash file

Default location: `~/.config/stash/stash.txt`, created on the first add. One entry per line, and one rule:

**Everything after the first `|` is the payload, verbatim. The words before it are what you search by, and what Alfred shows.** Without a `|`, the whole line is both.

```
pihole update finished                                   searched in full, copied in full
ssh prod web | ssh deploy@10.0.1.5                       search by ssh / prod / web, copy the command
logs api | tail -f app.log | grep ERROR                  only the first | splits, so pipes in the payload are fine
find pyc \ find . -name '*.pyc' -exec rm {} \;           \ works as the separator too
| echo a | wc                                            empty left side: a payload with pipes, searched by its own words
```

Rules:

- `|` and `\` are both separators, so use whichever your keyboard makes easier; only the first one on the line counts.
- Search words are split on spaces and commas; the payload is never searched.
- A separator with nothing after it (`note |`) copies the words themselves.
- Lines starting with `#` and blank lines are ignored, so comment and group freely. To stash something that starts with `#`, write `| #FF8800`.
- Whitespace around the separator is ignored, so you can align columns.
- The file is UTF-8; words in any script work (`кава coffee`). A stray non-UTF-8 byte won't break search, and add or delete keep such bytes exactly as they were.

A sample of what a real file can look like (the full one is in `examples/stash.txt`):

```
# shell one-liners: enter copies, shift-enter pastes
ssh prod web              | ssh deploy@10.0.1.5
k8s ctx staging kube      | kubectl config use-context staging
port listen who 8080      | lsof -nP -iTCP:8080 -sTCP:LISTEN | grep -v COMMAND
find py rm                \ find . -name '*.pyc' -exec rm {} \;

# links and paths: enter opens
grafana api latency       | https://grafana.example.com/d/api-latency
notes folder              | ~/notes
tally open                | alfred://runtrigger/com.anokhin.tally/open/

# text: enter copies
email work                | name.surname@example.com
reply thanks review       | Thanks for the review! I've addressed the comments, PTAL.

# plain lines: searched in full, copied in full
pihole update finished
wifi guest GuestNetwork-5G
```

## Searching

Type `st` (or `sta`, or `stash`) followed by any words. Each query word must match **some** word of an entry's left side; the order of query words doesn't matter, and entries may have more words than you typed.

A query word matches a stash word in one of four ways, strongest first:

| Query word | Stash word | Match | Score |
|---|---|---|---|
| `prod` | prod | whole word | 4 |
| `pro` | prod | start of word | 3 |
| `rod`, `4000` | prod, http://127.0.0.1:4000 | inside word | 2 |
| `prd`, `stg` | prod, staging | letters in order, inside one word | 1 |

Scores of all query words add up. Equal scores go to the entry with fewer words (the tighter match), then to the one higher in the file. Alfred also learns which results you pick and moves them up over time.

The last result is always **Add: …** for what you typed (see [Adding entries](#adding-entries)); it is left out of the examples below.

| You type | You get | Why |
|---|---|---|
| `st` | every entry, in file order | empty query browses the file |
| `st prod` | ssh prod web, k8s ctx prod kube | whole-word match |
| `st web ssh` | ssh prod web, ssh staging web | any order; prod is first in the file |
| `st stg` | ssh staging web, k8s ctx staging kube, wifi guest GuestNetwork-5G | letters in order inside *staging*; the stray hit in *GuestNetwork-5G* ranks last |
| `st k8 prd` | k8s ctx prod kube | `k8` starts *k8s*, `prd` is inside *prod* |
| `st lat` | grafana api latency | `lat` starts *latency* |
| `st grf lat` | grafana api latency | `grf` is inside *grafana* |
| `st 4000` | http://127.0.0.1:4000 | a plain line is searched in full, and `4000` is inside its one word |
| `st кав` | кава coffee order | Unicode works |
| `st finished` | pihole update finished | a plain line is searched in full |
| `st deploy` | only *Add* | the ssh payloads mention *deploy*, but payloads aren't searched |
| `st ssh prod staging` | only *Add* | every query word must match |
| `st kctx` | only *Add* | letters-in-order stays inside one word; type `st k ctx` |
| `st stgaing` | only *Add* | swapped letters aren't tolerated, dropped letters are |

Press ⇥ (Tab) on a result to put its words into the query.

## Actions on a result

What ↩ does depends on the payload:

| Payload | ↩ |
|---|---|
| `http://…`, `https://…`, `file://…` | opens it in the default app |
| `alfred://runtrigger/<bundle id>/<trigger>/?argument=…` | runs that workflow's external trigger |
| a path that exists (`~/notes`, `/Users/me/doc.pdf`) | opens it (⌥↩ in Finder is up to you: see below) |
| anything else | copies it to the clipboard |

The subtitle says which: an entry whose payload opens shows `Open · …`. Everything else is the same for every result:

| Keys | Action |
|---|---|
| ⇧↩ | Copy and paste the payload into the frontmost app |
| ⌘↩ | Open the stash in your editor at this entry's line (on *Add* or a hint: at the top) |
| ⌥↩ | Delete this entry from the file |
| ⌃ (hold) | Show the entry's line number and what ↩ will do |
| ⌘C | Copy the payload as written (Alfred's own copy shortcut) |
| ⌘L | Show the payload in Large Type |

The payload is copied literally: Alfred placeholders such as `{date}` inside it are not expanded. A shell one-liner is deliberately *not* run on ↩; ⇧↩ into a terminal you are looking at is one keystroke more and much harder to regret.

## Adding entries

There is no separate add keyword. Whatever you type after `st` is offered as a new entry in the **Add: …** result, whose subtitle previews the payload. Press ↩ on it and the line is appended to the file, confirmed by a notification.

- With no matches, *Add* is the only result, so a miss is ↩ away from being stored under the words you just searched for.
- With matches, *Add* is the last result: ↓ to it, or keep typing.
- As soon as you type a `|` or `\`, you are clearly writing an entry, so *Add* becomes the **first** result and ↩ stores it. The words before the separator are still searched, so you see at once whether such an entry already exists.

| You type after `st` | Stored line | Shown as | ↩ later |
|---|---|---|---|
| `ssh prod web \| ssh deploy@10.0.1.5` | same | ssh prod web | copies the command |
| `logs api \| tail -f app.log \| grep ERROR` | same | logs api | copies `tail -f app.log \| grep ERROR` |
| `grafana lat \| https://grafana.example.com/d/api-latency` | same | grafana lat | opens the dashboard |
| `http://127.0.0.1:4000` | same | http://127.0.0.1:4000 | opens it |
| `pihole update finished` | same | pihole update finished | copies it |

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

Every script of the copy needs the same export (search, add, delete, edit, open), because Alfred does not pass a script's environment on to the objects it is connected to.

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
python3 ~/.stash/run.py add 'logs api | kubectl logs -f deploy/api | grep -v health'
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
- Deciding whether a payload opens or copies costs one `stat` per shown result, never per entry.
- Python runs with `-S` (no `site` import) and the code avoids heavy modules: `dataclasses` alone costs ~12 ms and `pathlib` ~9 ms per start, so `NamedTuple`, `os.path` and `os.execvp` take their place.
- Alfred is set to run the script immediately and to cancel a still-running search when you type the next letter.

## Limitations

- Swapped letters (`stgaing`) don't match; dropped letters (`stgng`) do.
- Letters-in-order matching stays within one word: `kctx` won't find `k8s ctx`, `k ctx` will.
- Words are split on spaces and commas only, so `kube:` is a word and `kube` matches it as a prefix, not a whole word.
- Payloads are single lines.
- A path payload opens only if it exists when you search; a command that happens to start with `/` is copied, not run.
- It's a plain-text file: don't store secrets you wouldn't keep in a dotfile.

## Development

```bash
uv sync
uv run pytest                                       # 193 tests
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
| `stash/entries.py` | Split a line at its first separator into an `Entry` with its searchable text |
| `stash/matching.py` | One regex per query word, scoring, ranking |
| `stash/store.py` | Load entries, append, delete lines; atomic, symlink-safe writes |
| `stash/alfred.py` | Alfred Script Filter JSON: results and their copy/open action, the *Add* item, hints |
| `stash/cli.py` | Commands `search`, `add`, `delete`, `edit`, `open`; workflow variables |
| `run.py` | Entry point Alfred calls |
| `make_plist.py` | Source of `info.plist`: keywords, objects, connections, variables |
| `tests/` | pytest suite, including a structural check of `info.plist` |
| `bench.py` | End-to-end latency benchmark |
| `examples/stash.txt` | Sample stash |
