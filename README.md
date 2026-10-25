# Stash

Fuzzy keyword search over a plain-text stash you own, as an Alfred workflow.

- **Search** with any words, in any order, any subset of them, any part of a word: `st stg k8` finds `k8s ctx staging kube`.
- **Act**: ↩ copies the payload, or opens it when it is a URL, a path or an Alfred flow; ⇧↩ pastes it.
- **Add** by typing: whatever you searched for is always offered as a new entry, so a miss is one ↩ away from being stored.
- **Run** by typing: a hand-off, a link or a `{{blank}}` typed straight into the field gets a *Run* row that acts on it without storing anything.
- **Own the data**: one line per entry in text files you can edit, grep, sync and keep in git. The format is one rule: everything after the first `|` is the payload.
- **Scope** when the list gets long: every `name.txt` next to the main file is a scope; `st name/` searches inside it, and scoped entries still show up at the root.
- **Fill in the blanks**: a payload with `{{host}}` asks for `host` on ↩ and copies, opens or pastes the result; `{{date}}`, `{{time}}` and `{{clipboard}}` fill themselves.
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
- [The stash folder](#the-stash-folder)
- [Searching](#searching)
- [Scopes](#scopes)
- [Placeholders](#placeholders)
- [Running what you typed](#running-what-you-typed)
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
2. Alfred shows the configuration sheet. Python: the default is `/usr/bin/python3`, which macOS provides once the Xcode Command Line Tools are installed (`xcode-select --install`). To use another interpreter, set **Python** to its **absolute path**, for example `/opt/homebrew/bin/python3` or the output of `uv python find 3.12`.
3. Optionally point **Stash folder** at an existing folder and set **Editor** (see [Configuration](#configuration)); all of it can be changed later with **Configure Workflow…**.
4. If you will use `@keyword` hand-offs, run this once in Terminal and click **OK** when macOS asks whether Alfred may control Alfred:
   ```
   osascript -e 'tell application id "com.runningwithcrayons.Alfred" to search "st"'
   ```
   macOS asks the first time one app drives another through AppleScript, and when the request comes from a workflow script the dialog can fail to appear. Running it from Terminal makes it show up; the permission is remembered. If you skip this, the first hand-off posts a notification with the same line.

## Quick start

`st`, `sta` and `stash` are the same keyword; use whichever your fingers produce. ⌘⌥⌃⇧L (hyper + L) opens the stash too; change or clear it on the *Hotkey* node in the workflow.

```
st ssh prod web | ssh deploy@10.0.1.5     ↩ adds the entry
st prod                                   ↩ copies ssh deploy@10.0.1.5
st http://127.0.0.1:4000                  ↩ adds it; next time, st 4000 ↩ opens it
st                                        browse everything; ⌘↩ opens default.txt
```

To explore with sample data first, set `db_dir` to the `examples` folder that ships with the source.

## The stash folder

Default location: `~/.config/stash`. The root entries live in `default.txt` there, created on the first add; any other `name.txt` in the folder is a [scope](#scopes). Every file has one entry per line, and one rule:

**Everything after the first `|` is the payload, verbatim. The words before it are what you search by, and what Alfred shows.** Without a `|`, the whole line is both.

```
pihole update finished                                   searched in full, copied in full
ssh prod web | ssh deploy@10.0.1.5                       search by ssh / prod / web, copy the command
logs api | tail -f app.log | grep ERROR                  only the first | splits, so pipes in the payload are fine
find pyc \ find . -name '*.pyc' -exec rm {} \;           \ works as the separator too
| echo a | wc                                            empty left side: a payload with pipes, searched by its own words
```

Rules:

- `|` and `\` are both separators, so use whichever your keyboard makes easier; only the first one on the line counts. A `\` counts only with whitespace on both sides (or at the very start or end of the line), so `regex \d+`, `C:\Users\me` and `printf 'a\nb'` stay whole as plain lines.
- Search words are split on spaces and commas; the payload is never searched.
- A separator with nothing after it (`note |`) copies the words themselves.
- Lines starting with `#` and blank lines are ignored, so comment and group freely. To stash something that starts with `#`, write `| #FF8800`.
- Whitespace around the separator is ignored, so you can align columns.
- The file is UTF-8; words in any script work (`кава coffee`). A stray non-UTF-8 byte won't break search, and add or delete keep such bytes exactly as they were.

A sample of what a real file can look like (the full one is in `examples/default.txt`):

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

# hand-offs: enter opens Alfred with the other workflow's keyword (flows = "tally=t kobold=kb wisp=l")
delany books              | delany @kobold
lexer task                | parser lexer @tally

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
| `st` | every scope, then every entry in file order | empty query browses the stash |
| `st prod` | ssh prod web, k8s ctx prod kube | whole-word match |
| `st web ssh` | ssh prod web, ssh staging web | any order; prod is first in the file |
| `st stg` | ssh staging web, k8s ctx staging kube, wifi guest GuestNetwork-5G | letters in order inside *staging*; the same letters also occur inside *GuestNetwork-5G*, so it is listed too, last |
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

## Scopes

A scope is a second file in the stash folder: `~/.config/stash/checklists.txt` is the scope `checklists`. Its lines are ordinary entries; the file name is all that makes it a scope. A name must be something you can type before a slash, so letters, digits, `_` and `-`.

```
st                    the root entries  ·  then the entries of every scope
st ck                 checklists/  ·  root entries matching ck  ·  scoped entries matching ck  ·  Add: ck
st checklists/        everything in checklists.txt, like a bare st does for the root
st checklists/ rel    release checklist  ·  Add: rel
st checklists/ pack | passport, charger      ↩ appends to checklists.txt
st recipes/ pasta | 500g                     ↩ creates recipes.txt with that entry
```

Results come in three tiers, each ranked as in [Searching](#searching): scope rows whose names match what you typed, root entries, then entries from all scopes. A scope row has the 📒 icon, says how many entries it holds, and ⇥ or ↩ on it puts `checklists/ ` into the query, which is the whole mechanism: a query that starts with `name/` searches only that scope, and everything else (*Add*, ⌘↩, ⌥↩) acts on that scope's file. Backspace over the slash to leave. At the root, a scoped entry's subtitle starts with its scope (`checklists · …`); inside the scope it looks like any other entry.

A bare `st` lists entries only; turn on **List scopes** in the configuration to have it list every scope first.

A scope exists exactly when its file does. There is no "create scope": add the first entry under `name/` and the file appears, with the *Add* row saying so beforehand. To remove a scope, delete the file. ⌘↩ on a scope row opens its file; ⌥↩ does nothing there, since deleting a whole file is not something a keystroke should do.

Scopes do not nest.

## Actions on a result

What ↩ does depends on the payload:

| Payload | ↩ |
|---|---|
| `http://…`, `https://…`, `file://…` | opens it in the default app |
| `alfred://runtrigger/<bundle id>/<trigger>/?argument=…` | runs that workflow's external trigger |
| a path that exists (`~/notes`, `/Users/me/doc.pdf`) | opens it |
| `text @keyword` or `@keyword text` | opens Alfred with `keyword text`, so another workflow takes over (see below) |
| anything with `{{name}}` in it | asks for each name first, then does one of the above with the result (see [Placeholders](#placeholders)) |
| anything else | copies it to the clipboard |

The subtitle says which: `Open · …` or `→ kobold · delany`. Everything else is the same for every result:

| Keys | Action |
|---|---|
| ⇧↩ | Copy and paste the payload into the frontmost app |
| ⌘↩ | Open this entry's file in your editor at its line (on *Add* or a hint: at the top) |
| ⌥↩ | Delete this entry from its file |
| ⌃ (hold) | Show the entry's file and line number, and what ↩ will do (for a hand-off, the resolved call: `alfred: kb delany`) |
| ⌘C | Copy the payload as written (Alfred's own copy shortcut) |
| ⌘L | Show the payload in Large Type |

The payload is copied literally: Alfred's own placeholders such as `{date}` inside it are not expanded; Stash's `{{date}}` is (see [Placeholders](#placeholders)). A shell one-liner is deliberately *not* run on ↩; ⇧↩ into a terminal you are looking at is one keystroke more and much harder to regret.

### Handing off to another workflow

A payload that ends or starts with `@word` is a hand-off: ↩ opens Alfred with `word` as the keyword and the rest as its query, so the other workflow shows its own results and you pick there. Nothing needs to be set up in that workflow; it just sees its keyword typed.

```
delany @kb                  st delany ↩  →  Alfred shows  kb delany   (kobold lists the books)
parser lexer @t             st parser ↩  →  Alfred shows  t parser lexer   (tally offers to start it)
@t parser lexer             the same, keyword first
@l                          st @l ↩      →  Alfred shows  l   (wisp, newest first)
```

The first hand-off needs a one-time macOS permission (step 4 of [Install](#install)); until it is granted, ↩ posts a notification with the Terminal line that triggers the dialog, instead of silently doing nothing.

Write workflow names instead of keywords by listing aliases in the `flows` variable, for example `tally=t kobold=kb wisp=l`; then `parser lexer @tally` means the same as `parser lexer @t`. The subtitle shows the name as you wrote it (`→ tally · parser lexer`), ⌃ shows the resolved call (`alfred: t parser lexer`), and ⌘C still copies the payload as written.

Only a leading or trailing `@word` counts, so `me@example.com` and `mail me@example.com now` are copied as text. A payload that genuinely starts or ends with an `@handle` (`@here deploying now`) would be taken as a hand-off; ⌘C still copies it, or end the line with a full stop, or put a word before the handle.

## Placeholders

A payload can leave blanks to be filled when it is used:

```
ssh box        | ssh {{user=root}}@{{host}} -p {{port=22}}
jira ticket    | https://example.atlassian.net/browse/{{ticket}}
wrap code      | `{{clipboard}}`
standup        | {{date}} standup: {{done}} / {{next}}
```

`{{name}}` is a blank; `name` is letters, digits, `_` and `-`, so `{}`, `${VAR}`, `{"a": 1}` and `{{ not a name }}` are left alone. `{{name=value}}` gives it a default, which is used literally (nothing is evaluated). The same name twice is one blank.

Three names fill themselves and are never asked for: `{{date}}` is today as `2026-10-25`, `{{time}}` is now as `14:05`, and `{{clipboard}}` is the clipboard. You see what the first two become before you press anything: the subtitle of a result, and of the *Add* row while you type one, shows the payload with them resolved. The clipboard is read only when you press ↩, so what is on it never shows up in the results list and no search touches it.

↩ on an entry with other blanks opens one prompt per name, in order of first appearance. The row's title is `host (1/2): …` and its subtitle is the payload as it stands; the rows are what you have typed, the default if there is one, and the clipboard, in that order. ↩ takes the selected row and moves to the next name; on the last one ↩ does what the entry would normally do with the result: copy it, open it if it is a URL or a path, hand it off if it ends in `@keyword`. ⇧↩ on the entry, or on the last row, pastes instead. Esc abandons with nothing copied.

```
st box ↩                 user (1/3): root   (default)               ssh root@{{host}} -p {{port=22}}
                         user (1/3): 10.0.0.9   (clipboard)         ssh 10.0.0.9@{{host}} -p {{port=22}}
↩                        host (2/3): 10.0.0.9   (clipboard)         ssh root@10.0.0.9 -p {{port=22}}
db.example.com ↩         port (3/3): 22   (default)                 Copy · ssh root@db.example.com -p 22
↩                        copied: ssh root@db.example.com -p 22
```

The counter is how many ↩ remain, so with the clipboard holding the host and the defaults doing the rest it is three.

Entries without blanks are untouched by any of this; ↩ still copies on the spot.

## Running what you typed

Some things are worth doing once without storing them. When the query itself is a payload — it starts or ends with `@word`, it is a URL or an existing path, or it contains `{{…}}` — the first result is **Run: …**, which does with the text exactly what ↩ would do with an entry whose payload it was, and stores nothing:

```
st delany @kobold ↩        hands "delany" to kobold         (→ kobold · delany)
st @t 33333 ↩              hands "33333" to tally           (→ t · 33333)
st https://example.com ↩   opens it
st release {{date}} ↩      copies  release 2026-10-25
st ssh {{host}} ↩          asks for host, then copies
```

*Add* is still there, one row down, so ↓↩ stores it instead. A typed `|` means you are writing an entry, so there is no *Run* row then. ⌃ on the *Run* row says `Not stored`. Plain words never get a *Run* row; copying what you just typed is not worth a keystroke.

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

Entries are appended at the end of `default.txt`, or of the scope's file when the query starts with `name/`. Reorder or group them later in your editor; the files are the source of truth.

## Editing and deleting

- ⌘↩ on any result opens its file in your editor at that entry's line (with an editor that supports lines, see below); on the *Add* item or on a hint it opens the current file at the top.
- ⌥↩ on a search result deletes that line from its file. Deletion matches the line's content, so if you edited the file since the search, it reports *entry not found* instead of deleting the wrong line. Comments and other lines are kept as they are, and a file that is a symlink (to iCloud, Dropbox, a git repo) stays a symlink.

## Configuration

Set these in Alfred: open the workflow and press **Configure Workflow…** (the cog at the top right of the workflow, or right-click it in the list). Alfred also shows this sheet when you import the workflow. The fields are text fields with a default each, so leaving one blank keeps the default.

| Variable | Default | Meaning |
|---|---|---|
| `db_dir` | `~/.config/stash` | The stash folder: `default.txt` plus one `name.txt` per scope. `~` is expanded. |
| `editor` | `open -t {file}` | Command used by ⌘↩. `{file}` and `{line}` are filled in. |
| `max_results` | `50` | How many results Alfred receives. |
| `python` | `/usr/bin/python3` | Interpreter, 3.9 or newer. Absolute path, no `~`. |
| `flows` | empty | Aliases for `@word` hand-offs, as `name=keyword` pairs: `tally=t kobold=kb wisp=l`. |
| `show_scopes` | off | List every scope on a bare `st`. Typing part of a scope name shows its row either way. |

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

### Coming from 2.x

The stash used to be a single file, `~/.config/stash/stash.txt`. It is now a folder, and the file's name is the scope's name, so rename it once:

```bash
mv ~/.config/stash/stash.txt ~/.config/stash/default.txt
```

Until you do, it shows up as a scope called `stash`. If you had pointed `db_file` elsewhere, point `db_dir` at that file's folder and rename the file the same way.

### Several stashes

Make them scopes: one `name.txt` each in the stash folder. If you want a second keyword that opens straight inside one, copy the Script Filter in Alfred, give it the keyword, and prefix the query in its script: `… run.py search "links/ $1"`.

### Sync and history

Keep the folder wherever you like and point `db_dir` at it, or symlink it:

```bash
ln -s ~/Library/Mobile\ Documents/com~apple~CloudDocs/stash ~/.config/stash
```

Since it's plain text, `git init` in the folder gives you history and diffs for free.

### Use it from the terminal

In Alfred, right-click the workflow and choose **Open in Finder** to find its folder, then link it somewhere short (same command in bash and fish):

```bash
ln -s "$HOME/Library/Application Support/Alfred/Alfred.alfredpreferences/workflows/user.workflow.XXXX" ~/.stash
```

Search and copy the best match, in bash or fish (needs `jq`):

```bash
python3 ~/.stash/run.py search k8s prod | jq -r '.items[0].arg' | pbcopy
```

Add an entry, to the root or to a scope:

```bash
python3 ~/.stash/run.py add 'logs api | kubectl logs -f deploy/api | grep -v health'
python3 ~/.stash/run.py add 'checklists/ pack | passport, charger'
```

Fill a payload's blanks with `name=value` pairs (`{{date}}`, `{{time}}` and `{{clipboard}}` resolve on their own):

```bash
python3 ~/.stash/run.py fill 'ssh {{user=root}}@{{host}} on {{date}}' user=deploy host=10.0.0.1
ssh deploy@10.0.0.1 on 2026-10-25
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

About 25 ms of that is starting Python and importing modules, which no pure-Python workflow avoids; the rest is reading and parsing the files (~6 ms per 1,000 lines) and matching (~1.5 ms per 1,000 lines). Reproduce with `uv run python bench.py --python /usr/bin/python3`; add `--stress` for a vocabulary where most queries match most entries.

The design is deliberately the simple one: the files are parsed on every keystroke and there is no cache or index. That stays instant for the few hundred to few thousand entries a personal stash has. An earlier version cached the searchable text keyed by file checksum and scanned it with hand-tuned string checks, which held 10,000 entries at ~50 ms and 50,000 at ~100 ms, at the cost of an extra module and a cache directory; it is in the git history (tag `v1.0-cached`) if you ever need it.

What keeps it fast:

- Each query word compiles to one regex whose alternatives are ordered from whole word to in-word letters, so a single `match` returns both whether and how well the word matches, and the in-word pattern never backtracks.
- Deciding whether a payload opens or copies costs one `stat` per shown result, never per entry.
- Python runs with `-S` (no `site` import) and the code avoids heavy modules: `dataclasses` alone costs ~12 ms and `pathlib` ~9 ms per start, so `NamedTuple`, `os.path` and `os.execvp` take their place.
- Alfred is set to run the script immediately and to cancel a still-running search when you type the next letter.

## Limitations

- Swapped letters (`stgaing`) don't match; dropped letters (`stgng`) do.
- Letters-in-order matching stays within one word: `kctx` won't find `k8s ctx`, `k ctx` will.
- Words are split on spaces and commas only, so `kube:` is a word and `kube` matches it as a prefix, not a whole word.
- Payloads are single lines: there is no way to put a newline in one, and `\n` is copied as the two characters. A default inside `{{name=…}}` can't contain braces.
- Scopes do not nest, and a root entry whose first word ends in `/` (`foo/ bar`) can't be reached as such: `st foo/` means the scope `foo`.
- A path payload opens only if it exists when you search; a command that happens to start with `/` is copied, not run.
- It's a plain-text file: don't store secrets you wouldn't keep in a dotfile.

## Development

```bash
uv sync
make test           # pytest on the project interpreter                      (356 tests)
make test-system    # the same on /usr/bin/python3, the interpreter the workflow runs on
make lint           # ruff check + format
make check          # build dist/Stash.alfredworkflow and run it the way Alfred would
make bench          # latency per keystroke; PYTHON=/path/to/python3 to pick the interpreter
```

`make check` unzips the bundle into a temporary folder and drives every script from its `info.plist` through `bash`, exactly as Alfred does, against a throwaway stash: add with pipes, search, hand-off, edit, delete.

CI (`.github/workflows/ci.yml`) runs lint and the tests on Python 3.9 and 3.13 on Linux, then the tests and `make check` on macOS with `/usr/bin/python3`, and uploads the bundle. Every push to the default branch republishes it as the `latest` pre-release; a `v*` tag makes a proper release with notes. To cut one:

```bash
git tag v3.0.0 && git push origin v3.0.0
```

| Path | Responsibility |
|---|---|
| `stash/entries.py` | Split a line at its first separator into an `Entry` with its searchable text; the `name/` scope prefix |
| `stash/matching.py` | One regex per query word, scoring, ranking |
| `stash/store.py` | The stash folder: `default.txt` and the scope files; load, append, delete lines; atomic, symlink-safe writes |
| `stash/snippets.py` | `{{name}}` and `{{name=default}}` placeholders, the reserved `date`, `time` and `clipboard`, filling |
| `stash/alfred.py` | Alfred Script Filter JSON: results and their copy/open/hand-off/fill/resolve action, scope rows, the *Run* and *Add* items, prompt rows, hints |
| `stash/cli.py` | Commands `search`, `add`, `delete`, `edit`, `open`, `alfred`, `prompt`, `resolve`, `fill`; workflow variables |
| `run.py` | Entry point Alfred calls |
| `make_plist.py` | Source of `info.plist`: keywords, the prompt filter, the router, connections, variables |
| `scripts/build.py`, `scripts/smoke.py`, `scripts/make_icons.py` | Build the bundle; run it the way Alfred would; draw `scope.png` (📒 on the icon's tile) |
| `Makefile`, `.github/workflows/ci.yml` | The targets above, and CI that runs them |
| `tests/` | pytest suite, including a structural check of `info.plist` |
| `bench.py` | End-to-end latency benchmark |
| `examples/` | Sample stash folder: `default.txt` and the scope `checklists.txt` |
