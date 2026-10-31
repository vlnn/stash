# Stashes

Fuzzy keyword search over plain-text stashes you own, as an Alfred workflow.

- **Search** with any words, in any order, any subset of them, any part of a word: `st stg k8` finds `k8s ctx staging kube`. A word the label doesn't have is looked for in the payload, so `st use-context` finds it too.
- **Act**: ↩ copies the payload, or opens it when it is a URL, a path or an Alfred flow; ⇧↩ pastes it.
- **Add** by typing: whatever you searched for is always offered as a new entry, so a miss is one ↩ away from being stored.
- **Run** by typing: a hand-off, a link or a `{{blank}}` typed straight into the field gets a *Run* row next to what it found, acting on the text without storing it.
- **Own the data**: one line per entry in text files you can edit, grep, sync and keep in git. The format is one rule: everything after the first `|` is the payload; the words before it are what you search by first.
- **Several stashes** when the list gets long: every `name.txt` in the folder is a stash; `st name/` searches one, and a bare `st` searches all of them.
- **Dated**: every line you add is stamped with the day, in the line itself (`2026-10-26: …`). `st today/`, `st yesterday/`, `st tomorrow/`, `st week/`, `st next-week/`, `st last-month/`, `st year/` and the rest of that grid are views over every stash by that day; nothing is ever moved, rolled or deleted to make them work. `st tomorrow/ dentist ↩` plans a line a day ahead, and the calendar brings it into `today/`.
- **Fill in the blanks**: a payload with `{{host}}` asks for `host` on ↩ and copies, opens or pastes the result; `{{date}}`, `{{time}}` and `{{clipboard}}` fill themselves.
- **Fast**: no dependencies, built to stay well under Alfred's "instant" threshold for a few thousand entries.

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

A longer, task-by-task walkthrough with animated examples is in [docs/MANUAL.md](docs/MANUAL.md).

## Contents

- [Install](#install)
- [Quick start](#quick-start)
- [The stashes folder](#the-stashes-folder)
- [Searching](#searching)
- [Several stashes](#several-stashes)
- [Dates and views](#dates-and-views)
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

1. Double-click `Stashes.alfredworkflow` and press **Import**.
2. Alfred shows the configuration sheet. Python: the default is `/usr/bin/python3`, which macOS provides once the Xcode Command Line Tools are installed (`xcode-select --install`). To use another interpreter, set **Python** to its **absolute path**, for example `/opt/homebrew/bin/python3` or the output of `uv python find 3.12`.
3. Optionally point **Stashes folder** at an existing folder and set **Editor** (see [Configuration](#configuration)); all of it can be changed later with **Configure Workflow…**.
4. If you will use `@keyword` hand-offs, run this once in Terminal and click **OK** when macOS asks whether Alfred may control Alfred:
   ```
   osascript -e 'tell application id "com.runningwithcrayons.Alfred" to search "st"'
   ```
   macOS asks the first time one app drives another through AppleScript, and when the request comes from a workflow script the dialog can fail to appear. Running it from Terminal makes it show up; the permission is remembered. If you skip this, the first hand-off posts a notification with the same line.

## Quick start

`st`, `sta` and `stash` are the same keyword; use whichever your fingers produce. ⌘⌥⌃⇧L (hyper + L) opens it too; change or clear it on the *Hotkey* node in the workflow.

```
st ssh prod web | ssh deploy@10.0.1.5     ↩ adds the entry
st prod                                   ↩ copies ssh deploy@10.0.1.5
st http://127.0.0.1:4000                  ↩ adds it; next time, st 4000 ↩ opens it
st today/                                 what you added today, then the undated evergreens
st                                        browse everything; ⌘↩ opens default.txt
```

To explore with sample data first, set `db_dir` to the `examples` folder that ships with the source.

## The stashes folder

Default location: `~/.config/stash`. Every `name.txt` in it is a stash. `default.txt` is the one you land in and the one a plain `st … ↩` adds to, created on the first add; the others are reached as `name/` (see [Several stashes](#several-stashes)). Every file has one entry per line, and one rule:

**Everything after the first `|` is the payload, verbatim. The words before it are what you search by, and what Alfred shows.** Without a `|`, the whole line is both.

```
pihole update finished                                   searched in full, copied in full
ssh prod web | ssh deploy@10.0.1.5                       search by ssh / prod / web, copy the command
logs api | tail -f app.log | grep ERROR                  only the first | splits, so pipes in the payload are fine
find pyc \ find . -name '*.pyc' -exec rm {} \;           \ works as the separator too
| echo a | wc                                            empty left side: a payload with pipes, searched by its own words
2026-10-26: k8s ctx prod | kubectl config use-context prod   a stamp: the day the line was added, written by the tool
```

A line the tool added starts with a **stamp**, `YYYY-MM-DD:` and a space; the rule above applies to what follows it. The stamp is never shown in the title and never searched; it is what `today/`, `week/` and the other views filter by (see [Dates and views](#dates-and-views)). A line without one, such as every line written before this version or by hand, is undated and belongs to every view.

Rules:

- `|` and `\` are both separators, so use whichever your keyboard makes easier; only the first one on the line counts. A `\` counts only with whitespace on both sides (or at the very start or end of the line), so `regex \d+`, `C:\Users\me` and `printf 'a\nb'` stay whole as plain lines.
- Search words are split on spaces and commas. The payload is searched too, but only as a fallback (see [Searching](#searching)).
- A separator with nothing after it (`note |`) copies the words themselves.
- Lines starting with `#` and blank lines are ignored, so comment and group freely. To stash something that starts with `#`, write `| #FF8800`. After a stamp the same holds: `2026-10-26: # note` is a comment, `2026-10-26: | #FF8800` an entry.
- A stamp is exactly `YYYY-MM-DD:` at the start of the line (a real month and day; `2026-13-01:` is just words). Only the first one counts: a date in the text, with or without a colon, is an ordinary word, so `2026-10-26: 2025-05-20 great day` is searched by `2025-05-20`, `great` and `day`.
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

# what the tool appends: stamped with the day, otherwise the same lines
2026-10-25: visit bank    | bring the signed form
2026-10-26: zoo visit     | 10:00, meet at the east gate
2026-10-26: k8s ctx prod  | kubectl config use-context prod
```

## Searching

Type `st` (or `sta`, or `stash`) followed by any words. Each query word must match **some** word of an entry's left side, or failing that be found somewhere in its payload; the order of query words doesn't matter, and entries may have more words than you typed.

A query word matches a word of the label in one of four ways, strongest first, and falls back to the payload:

| Query word | Matches | How | Score |
|---|---|---|---|
| `prod` | prod | whole label word | 8 |
| `pro` | prod | start of a label word | 6 |
| `rod`, `4000` | prod, http://127.0.0.1:4000 | inside a label word | 4 |
| `prd`, `stg` | prod, staging | letters in order, inside one label word | 2 |
| `deploy`, `{{date}}` | … \| ssh deploy@10.0.1.5 | plain text anywhere in the payload, case-insensitive | 1 |

Scores of all query words add up, so an entry found through its label always comes before one found only through its payload, however weak the label match. The payload is searched as written (`{{date}}` finds every entry that uses it), with no letter-dropping: `dply` does not find `deploy`. Equal scores go first to the fresher line: one stamped today, then one with no stamp, then older ones newest first (see [Dates and views](#dates-and-views)); after that to the entry with fewer label words (the tighter match), then to the one higher in the file. Alfred also learns which results you pick and moves them up over time.

The last result is always **Add: …** for what you typed (see [Adding entries](#adding-entries)); it is left out of the examples below.

| You type | You get | Why |
|---|---|---|
| `st` | every entry in file order, `default.txt` first | empty query browses everything |
| `st prod` | ssh prod web, k8s ctx prod kube | whole-word match |
| `st web ssh` | ssh prod web, ssh staging web | any order; prod is first in the file |
| `st stg` | ssh staging web, k8s ctx staging kube, wifi guest GuestNetwork-5G | letters in order inside *staging*; the same letters also occur inside *GuestNetwork-5G*, so it is listed too, last |
| `st k8 prd` | k8s ctx prod kube | `k8` starts *k8s*, `prd` is inside *prod* |
| `st lat` | grafana api latency | `lat` starts *latency* |
| `st grf lat` | grafana api latency | `grf` is inside *grafana* |
| `st 4000` | http://127.0.0.1:4000 | a plain line is searched in full, and `4000` is inside its one word |
| `st кав` | кава coffee order | Unicode works |
| `st finished` | pihole update finished | a plain line is searched in full |
| `st deploy` | ssh prod web, ssh staging web | no label has it; both payloads do |
| `st k8 config` | k8s ctx staging kube | `k8` from the label, `config` from `kubectl config use-context` |
| `st ssh prod staging` | only *Add* | every query word must match |
| `st kctx` | only *Add* | letters-in-order stays inside one word; type `st k ctx` |
| `st stgaing` | only *Add* | swapped letters aren't tolerated, dropped letters are |
| `st visit` | zoo visit, visit bank | both whole-word; the one stamped today comes first, see [Dates and views](#dates-and-views) |
| `st 2026-10-26` | only *Add* | the stamp is not a word; `st 2026-10-26/` is how you ask for that day |

Press ⇥ (Tab) on a result to put its words into the query.

## Several stashes

A stash is a file in the folder: `~/.config/stash/checklists.txt` is the stash `checklists`. Its lines are ordinary entries; the file name is all there is to it. A name must be something you can type before a slash, so letters, digits, `_` and `-`.

```
st                    the entries of default  ·  then the entries of every other stash
st ck                 checklists/  ·  default entries matching ck  ·  other entries matching ck  ·  Add: ck
st checklists/        everything in checklists.txt, like a bare st does for the root
st checklists/ rel    release checklist  ·  Add: rel
st checklists/ pack | passport, charger      ↩ appends to checklists.txt
st recipes/ pasta | 500g                     ↩ creates recipes.txt with that entry
```

Results come in three tiers, each ranked as in [Searching](#searching): stash rows whose names match what you typed, entries of `default`, then entries from every other stash. A stash row has the 📒 icon, says how many entries it holds, and ⇥ or ↩ on it puts `checklists/ ` into the query, which is the whole mechanism: a query that starts with `name/` searches only that stash, and everything else (*Add*, ⌘↩, ⌥↩) acts on its file. Backspace over the slash to leave. Seen from a bare `st`, an entry's subtitle starts with its stash (`checklists · …`); inside `checklists/` it looks like any other entry.

A bare `st` lists entries only; turn on **List stashes** in the configuration to have it list every stash first. The views of [Dates and views](#dates-and-views) get the same rows (`today/`, `week/`, …) once you have typed two or more letters of their name, at most two of them at a time (`st la` lists `last-week/` and `last-month/`; `st last-q` reaches `last-quarter/`), never on a bare `st`.

A stash exists exactly when its file does. There is no "create stash": add the first entry under `name/` and the file appears, with the *Add* row saying so beforehand. To remove one, delete the file. ⌘↩ on a stash row opens its file; ⌥↩ does nothing there, since deleting a whole file is not something a keystroke should do.

Stashes do not nest.

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
| ⌥↩ | Delete this entry: comment it out in its file with the day |
| ⌃ (hold) | Show the entry's file and line number, and what ↩ will do (for a hand-off, the resolved call: `alfred: kb delany`) |
| ⌘C | Copy the payload as written (Alfred's own copy shortcut) |
| ⌘L | Show the payload in Large Type |

The payload is copied literally: Alfred's own placeholders such as `{date}` inside it are not expanded; Stashes' `{{date}}` is (see [Placeholders](#placeholders)). A shell one-liner is deliberately *not* run on ↩; ⇧↩ into a terminal you are looking at is one keystroke more and much harder to regret.

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

## Dates and views

Every line the tool adds is stamped with the day it was added, and sixteen names, plus any date, are **views** that filter every stash by that stamp. A view looks like a stash (`st today/`, a `today/` row when you type `tod`, an *Add* row that works) but is not one: it has no file, nothing is moved into or out of it, and nothing happens at midnight. The windows are calendar periods, so `week/` is Monday to Sunday of this week, not the last seven days, and `next-week/` is the Monday to Sunday after it.

| View | Holds lines stamped | On Monday 2026-10-26 |
|---|---|---|
| `yesterday/` `today/` `tomorrow/` | that day | 2026-10-25 · 2026-10-26 · 2026-10-27 |
| `last-week/` `week/` `next-week/` | the ISO week, Monday to Sunday | 10-19 – 10-25 · 10-26 – 11-01 · 11-02 – 11-08 |
| `last-month/` `month/` `next-month/` | the calendar month | September · October · November |
| `last-quarter/` `quarter/` `next-quarter/` | the calendar quarter | Jul – Sep · Oct – Dec · Jan – Mar 2027 |
| `last-year/` `year/` `next-year/` | the calendar year | 2025 · 2026 · 2027 |
| `decade/` | this decade, `2020`–`2029` | 2020-01-01 – 2029-12-31 |
| `2026-10-20/` | that day, past or future | 2026-10-20 |

Every view also holds every **undated** line: a line without a stamp is an evergreen and belongs to every window, so `st today/ ssh` finds the `ssh prod web` you wrote by hand last year as well as the one you added this morning.

### The stamp

```
st zoo visit | 10:00 east gate    ↩  appends   2026-10-26: zoo visit | 10:00 east gate   to default.txt
st recipes/ pasta | 500g          ↩  appends   2026-10-26: pasta | 500g                   to recipes.txt
```

- The stamp is the day the tool wrote the line, in local time; the day changes at 00:00. It is written once and never touched again: the tool does not restamp, move, age out or delete anything. To change a stamp, edit the file; to remove one, delete it from the line.
- What you type is never a stamp. `st 2026-10-20: call dentist ↩` stores `2026-10-26: 2026-10-20: call dentist`, found by `st dentist` and by `st 2026-10-20` (a word now), shown as `2026-10-20: call dentist`, and held by `today/`, not by `2026-10-20/`.
- A stamp can be ahead of today. `st tomorrow/ dentist ↩` writes `2026-10-27: dentist`; tonight it is in `tomorrow/`, `week/` and `month/`, tomorrow morning it is in `today/`, the day after in `yesterday/`, and so on back through `week/` and `month/` as the calendar moves past it. Nothing moves the line; the day changes.
- Lines that predate this version, and lines you write in the editor without a stamp, are undated. There is nothing to migrate: they keep working as before and show up in every view. If you want a whole file to carry one date, a one-liner does it: `sed -i '' -e '/^[^#]/ s/^/2026-01-01: /' ~/.config/stash/default.txt`.

### Searching a view

A query that starts with a view name searches the lines the view holds, across every stash, and nothing else:

```
st today/                  zoo visit  ·  k8s ctx prod  ·  ssh prod web  ·  grafana api latency  ·  …   (today's, then every undated line)
st today/ visit            zoo visit  ·  Add: visit            (visit bank is yesterday's and visit vet tomorrow's, so neither is here)
st yesterday/ visit        visit bank  ·  Add: visit
st tomorrow/ visit         visit vet  ·  Add: visit
st week/ visit             zoo visit  ·  visit vet  ·  visit tax  ·  Add: visit      (today, then the rest of the week; bank was Sunday, last week)
st next-week/              review budget  ·  ssh prod web  ·  …    (next Monday to Sunday soonest first, then every undated line)
st 2026-10-25/             visit bank  ·  ssh prod web  ·  …    (that day, then every undated line)
st week/ pasta             pasta  ·  Add: pasta                 (recipes/ is searched too; the subtitle says recipes · today · 500g)
st tod                     today/  ·  Add: tod                  (the row; ⇥ or ↩ enters the view)
st ye                      yesterday/  ·  year/  ·  Add: ye     (two letters on: every view starting with them, two at most)
st next                    next-week/  ·  next-month/  ·  Add: next                (next-q reaches the other two)
```

Inside a view, results come in **calendar order around today**: today's lines, then the rest of the window ahead of today soonest first, then the part of the window already gone newest first, then the undated lines in file order. So `st next-week/` reads Monday to Sunday, `st yesterday/` is yesterday's lines then the evergreens, and `st week/` on a Wednesday is today, Thursday to Sunday, Tuesday, Monday, evergreens. With a query, the usual scores decide and freshness breaks the ties. The subtitle of a dated line says how old it is, after the stash it lives in: `today`, `1d`, `6d`, `1w`, `3w`, `1mo`, `11mo`, `1y`, `10y`; a date ahead of today shows as written (`2026-10-27`), since `st tomorrow/` is the way to ask what is planned. Undated lines show no age.

```
st visit                   zoo visit          today · 10:00 east gate
                           visit vet          2026-10-27 · the vet
                           visit tax          2026-10-30 · friday
                           visit grandma      every sunday                 (undated)
                           visit opera        2026-11-15 · next month
                           visit bank         1d · bring the signed form
                           visit dentist      1w · last monday
                           visit museum       3w · september
                           visit paris        9mo · last year
```

That order is the freshness tiebreak at the root, and it only breaks ties: among equal matches, a line stamped today comes first, then lines up to the Sunday of next week soonest first (what `tomorrow/` and `next-week/` hold), then undated lines, then anything further ahead soonest first, then the past newest first. A stronger match still wins over a fresher one: `st visit` ranks an old whole-word `visit` above today's `visits`. Nothing decays and nothing is hidden; an old plan line is simply listed after the evergreens that match as well, and next month's plan after them too, until next month is next week.

### Adding under a view

The *Add* row under a view appends to `default.txt`, since a view has no file. The current period (`today/`, `week/`, `month/`, `quarter/`, `year/`, `decade/`) stamps today; every other view stamps the **first day of its window**, which is how a line is planned ahead or backdated without an editor:

```
st today/ zoo visit ↩              2026-10-26: zoo visit            in default.txt
st tomorrow/ dentist ↩             2026-10-27: dentist              in tomorrow/ tonight, in today/ tomorrow
st next-week/ review budget ↩      2026-11-02: review budget        next Monday; in next-week/ now, in week/ from Monday
st next-month/ renew passport ↩    2026-11-01: renew passport       the 1st of next month
st next-quarter/ plan q1 ↩         2027-01-01: plan q1
st yesterday/ call dentist ↩       2026-10-25: call dentist         in default.txt, held by yesterday/
st last-week/ fixed the leak ↩     2026-10-19: fixed the leak       last Monday
st 2026-10-20/ paid rent ↩         2026-10-20: paid rent            in default.txt, held by 2026-10-20/
st 2026-12-24/ buy tree ↩          2026-12-24: buy tree             any date works, ahead or behind
st week/ zoo visit ↩               2026-10-26: zoo visit            week/ means today
st recipes/ pasta | 500g ↩         2026-10-26: pasta | 500g         in recipes.txt, held by today/ as well
```

A planned line moves through the views as the calendar does and nothing else happens to it: when its day comes it is in `today/`, the day after in `yesterday/`, then in `week/` and `month/` as a past line. A planned line you never delete does not nag; it is in `yesterday/` with a `1d` in its subtitle, and ⌥↩ there is the end of it.

⌘↩ on a view's *Add* row or on a view row opens `default.txt`; ⌘↩ on an entry opens the entry's own file at its line, and ⌥↩ deletes it from there, stamp and all, as usual.

### Reserved names

`today`, `yesterday`, `tomorrow`, `week`, `month`, `quarter`, `year`, `decade`, their `last-` and `next-` forms (`last-week`, `next-week`, `last-month`, `next-month`, `last-quarter`, `next-quarter`, `last-year`, `next-year`) and anything shaped like a date are views, so they cannot be stashes: `st week/ x ↩` adds to `default.txt`, and no `week.txt` is ever created. If a file with one of those names already exists in the folder, the view wins: `st week/` shows a hint saying `week.txt is hidden behind the week/ view`, the file's lines still turn up in a bare `st` and in whatever views their stamps allow, and renaming the file makes it a stash again.

### A day with views

One way to use them: capture into `today/` as things come up, plan ahead into `tomorrow/` and `next-week/`, look at `yesterday/` in the morning, delete what is done with ⌥↩. Nothing carries forward by itself; a leftover you still want is one ⇥ ↩ away (⇥ puts its words into the query, ↩ on *Add* stores it again with today's stamp, and the old line stays where it was, dated), or one `st tomorrow/ … ↩` if it is for tomorrow. `week/` is the plan for the week and, by Friday, its review; `next-week/` is Friday's planning; `month/` the retrospective; and a bare `st` still finds everything, with the age or the date in the subtitle so a stale plan line is easy to spot and delete.

```
st today/ call dentist ↩           morning: three things into today/
st today/ ship auth tests ↩
st today/ reply anna ↩
st tomorrow/ pick up parcel ↩      and one for tomorrow; it shows in today/ when tomorrow comes
st next-week/ 1:1 anna prep ↩      stamped next Monday
st today/                          during the day: the plan, ↩ opens or copies a line, ⌥↩ clears it when done
st yesterday/                      next morning: what was left; ⇥ ↩ on a line to take it into today
st week/                           the week: today, the days ahead, the days gone
st next-week/                      friday afternoon: what next week already holds
```

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

Stashes is for stashing first and running second: ↩ on an entry you found runs it, and whatever you typed is otherwise offered as a new entry. One exception: when the query itself is a payload — it starts or ends with `@word`, it is a URL or an existing path, or it contains `{{…}}` — *and* it found something, a **Run: …** row sits between the matches and *Add*. It does with the text exactly what ↩ would do with an entry whose payload it was, and stores nothing:

```
st delany @kobold          delany books  ·  Run: delany @kobold  ·  Add: delany @kobold
                           ↩ opens the entry you found; ↓↩ hands "delany" to kobold instead  (→ kobold · delany)
st @t 33333                lexer task  ·  Run: @t 33333  ·  Add: @t 33333
st release {{date}}        release notes  ·  Run: release {{date}}  ·  Add: release {{date}}     ↓↩ copies  release 2026-10-25
```

With no match there is no *Run* row: new text is added, and you run it from there afterwards. A typed `|` means you are writing an entry, so there is no *Run* row then either. ⌃ on the *Run* row says `Not stored`. Plain words never get a *Run* row; copying what you just typed is not worth a keystroke.

## Adding entries

There is no separate add keyword. Whatever you type after `st` is offered as a new entry in the **Add: …** result, whose subtitle previews the payload. Press ↩ on it and the line is appended to the file, confirmed by a notification.

- With no matches, *Add* is the only result, so a miss is ↩ away from being stored under the words you just searched for.
- With matches, *Add* is the last result: ↓ to it, or keep typing.
- As soon as you type a `|` or `\`, you are clearly writing an entry, so *Add* becomes the **first** result and ↩ stores it. The words before the separator are still searched, so you see at once whether such an entry already exists.
- With nothing before the separator (`st | echo a | wc`, a payload searched by its own words) there is nothing to search for, so *Add* is the **only** result. Anything else would be the whole stash under it, and Alfred floats the entries it has learned above a row it has never seen.

| You type after `st` | Stored line (on 2026-10-26) | Shown as | ↩ later |
|---|---|---|---|
| `ssh prod web \| ssh deploy@10.0.1.5` | `2026-10-26: ssh prod web \| ssh deploy@10.0.1.5` | ssh prod web | copies the command |
| `logs api \| tail -f app.log \| grep ERROR` | `2026-10-26: logs api \| tail -f app.log \| grep ERROR` | logs api | copies `tail -f app.log \| grep ERROR` |
| `grafana lat \| https://grafana.example.com/d/api-latency` | `2026-10-26: grafana lat \| https://…` | grafana lat | opens the dashboard |
| `http://127.0.0.1:4000` | `2026-10-26: http://127.0.0.1:4000` | http://127.0.0.1:4000 | opens it |
| `pihole update finished` | `2026-10-26: pihole update finished` | pihole update finished | copies it |
| `\| echo a \| wc` | `2026-10-26: \| echo a \| wc` | echo a \| wc | copies it; the only row while you type it |
| `yesterday/ call dentist` | `2026-10-25: call dentist` | call dentist | copies it; held by `yesterday/` |

Entries are appended at the end of `default.txt`, or of `name.txt` when the query starts with `name/`, each with the day's stamp in front (see [Dates and views](#dates-and-views)). Reorder or group them later in your editor; the files are the source of truth.

## Editing and deleting

- ⌘↩ on any result opens its file in your editor at that entry's line (with an editor that supports lines, see below); on the *Add* item or on a hint it opens the current stash at the top.
- ⌥↩ on a search result deletes that line from its file by commenting it out in place: `k8s ctx | kubectl …` becomes `# deleted 2026-10-31: k8s ctx | kubectl …`, which search never sees and the views never hold. Nothing is removed, so a slip of the keystroke is undone by taking the prefix off in your editor, git diffs stay readable, and line numbers below it do not move. Deletion matches the line's content, stamp included, so if you edited the file since the search, it reports *entry not found* instead of deleting the wrong line. Comments and other lines are kept as they are, and a file that is a symlink (to iCloud, Dropbox, a git repo) stays a symlink. Delete the comments from the file whenever you like.
- The stamp is yours to edit like the rest of the line: change the date and the line moves to that day's views, delete it and the line becomes an evergreen that every view holds.

## Configuration

Set these in Alfred: open the workflow and press **Configure Workflow…** (the cog at the top right of the workflow, or right-click it in the list). Alfred also shows this sheet when you import the workflow. The fields are text fields with a default each, so leaving one blank keeps the default.

| Variable | Default | Meaning |
|---|---|---|
| `db_dir` | `~/.config/stash` | The stashes folder: one `name.txt` per stash, `default.txt` being the one you land in. `~` is expanded. |
| `editor` | `open -t {file}` | Command used by ⌘↩. `{file}` and `{line}` are filled in. |
| `max_results` | `50` | How many results Alfred receives. |
| `python` | `/usr/bin/python3` | Interpreter, 3.9 or newer. Absolute path, no `~`. |
| `flows` | empty | Aliases for `@word` hand-offs, as `name=keyword` pairs: `tally=t kobold=kb wisp=l`. |
| `show_stashes` | off | List every stash on a bare `st`. Typing part of a stash name shows its row either way; a view row needs two letters of its name and is never listed on a bare `st`. |

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

### Coming from Stash 3.0

Only the name changed: the workflow is *Stashes*, and what the 3.0 README called a scope is a stash. The bundle id, the keywords, the folder and every setting are the same, so importing `Stashes.alfredworkflow` updates the installed workflow in place. The setting *List scopes* became *List stashes* (`show_stashes`); if you had turned it on, turn it on again. The repository moved to `github.com/vlnn/stashes`; the old address redirects.

### Coming from 2.x

There used to be a single file, `~/.config/stash/stash.txt`. It is now a folder of stashes, and the file's name is the stash's name, so rename it once:

```bash
mv ~/.config/stash/stash.txt ~/.config/stash/default.txt
```

Until you do, it shows up as a stash called `stash`. If you had pointed `db_file` elsewhere, point `db_dir` at that file's folder and rename the file the same way.

### A keyword per stash

If you want a second keyword that opens straight inside one, copy the Script Filter in Alfred, give it the keyword, and prefix the query in its script: `… run.py search "links/ $1"`.

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

Views are queries like any other, so today's plan as a list, or everything from one day:

```bash
python3 ~/.stash/run.py search 'today/' | jq -r '.items[] | select(.uid) | .title'
python3 ~/.stash/run.py search '2026-10-20/ visit' | jq -r '.items[] | select(.uid) | "\(.title)\t\(.subtitle)"'
```

Add an entry, to `default` or to another stash, or backdated under a view; each gets its stamp:

```bash
python3 ~/.stash/run.py add 'logs api | kubectl logs -f deploy/api | grep -v health'
python3 ~/.stash/run.py add 'checklists/ pack | passport, charger'
python3 ~/.stash/run.py add 'yesterday/ paid rent'
```

Fill a payload's blanks with `name=value` pairs (`{{date}}`, `{{time}}` and `{{clipboard}}` resolve on their own):

```bash
python3 ~/.stash/run.py fill 'ssh {{user=root}}@{{host}} on {{date}}' user=deploy host=10.0.0.1
ssh deploy@10.0.0.1 on 2026-10-25
```

Save the command you just ran under some keywords, so the next time it's one `st` away.

fish, in `~/.config/fish/functions/stash.fish`:

```fish
function stash --description 'Stash the previous command under the given keywords'
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
- The payload fallback is a plain substring test on a lowercased copy made at parse time, about 2 ms per 10,000 entries on top of the label search.
- A stamp costs one anchored regex match per line at parse time and one integer per hit at ranking time; the calendar windows are computed once per keystroke with integer day counts, so neither `datetime` (~1 ms to import on Python 3.9) nor the clock is involved beyond reading today's date. The benchmark stamps half of its lines.
- Python runs with `-S` (no `site` import) and the code avoids heavy modules: `dataclasses` alone costs ~12 ms and `pathlib` ~9 ms per start, so `NamedTuple`, `os.path` and `os.execvp` take their place.
- Alfred is set to run the script immediately and to cancel a still-running search when you type the next letter.

## Limitations

- Swapped letters (`stgaing`) don't match; dropped letters (`stgng`) do.
- Letters-in-order matching stays within one word: `kctx` won't find `k8s ctx`, `k ctx` will. Payloads are matched as plain text only: `dply` won't find `deploy`.
- Words are split on spaces and commas only, so `kube:` is a word and `kube` matches it as a prefix, not a whole word.
- Payloads are single lines: there is no way to put a newline in one, and `\n` is copied as the two characters. A default inside `{{name=…}}` can't contain braces.
- Stashes do not nest, and an entry whose first word ends in `/` (`foo/ bar`) can't be reached as such: `st foo/` means the stash `foo`.
- A path payload opens only if it exists when you search; a command that happens to start with `/` is copied, not run.
- A stamp is a day, not a time, in the local time zone of the machine that wrote it; the day turns at 00:00, so a line added at 00:30 is already today's. Views are calendar windows and nothing else: there is no "last 7 days", no "this week so far", and no window shorter than a day.
- A view holds every undated line, so `st today/` on an old stash lists all of it; the evergreens come after today's lines.
- `today`, `yesterday`, `tomorrow`, `week`, `month`, `quarter`, `year`, `decade`, their `last-` and `next-` forms and dates are not available as stash names.
- "Comes up first" means the calendar: a line stamped within next week ranks above the evergreens, a line stamped the Monday after does not, even when that is two days away. There is no rolling horizon.
- It's a plain-text file: don't store secrets you wouldn't keep in a dotfile.

## Development

```bash
uv sync
make test           # pytest on the project interpreter                      (664 tests)
make test-system    # the same on /usr/bin/python3, the interpreter the workflow runs on
make lint           # ruff check + format
make check          # build dist/Stashes.alfredworkflow and run it the way Alfred would
make bench          # latency per keystroke; PYTHON=/path/to/python3 to pick the interpreter
make docs           # regenerate everything under docs/: the GIFs the manual embeds
make gifs           # draw docs/gifs/*.gif, one frame per keystroke of each docs/scenarios.py scenario, dark and light
```

`make gifs` renders what Alfred would show, from the Script Filter JSON `run.py search` prints, as the query of each scenario is typed key by key against `docs/stashes/`, once in a dark and once in a light scheme; the same scenarios are asserted by `tests/test_scenarios.py`, so a GIF only shows what the suite checks. Scenarios that depend on the calendar pin their day (`DOCS_DAY`), so the dated lines in `docs/stashes/default.txt` land on the same frames every time. `docs/MANUAL.md` embeds the light GIF of each scenario and switches to the dark one for readers whose browser prefers a dark scheme.

`make check` unzips the bundle into a temporary folder and drives every script from its `info.plist` through `bash`, exactly as Alfred does, against a throwaway stash: add with pipes, search, hand-off, edit, delete, the views.

CI (`.github/workflows/ci.yml`) runs lint and the tests on Python 3.9 and 3.13 on Linux, then the tests and `make check` on macOS with `/usr/bin/python3`, and uploads the bundle. Every push to the default branch republishes it as the `latest` pre-release; a `v*` tag makes a proper release with notes. To cut one:

```bash
git tag v3.1.0 && git push origin v3.1.0
```

| Path | Responsibility |
|---|---|
| `stash/entries.py` | Split a line into its stamp and, at the first separator, an `Entry` with its searchable text; the `name/` prefix |
| `stash/views.py` | The view names as period × offset, their calendar windows (integer day counts, no `datetime`), the age word, the `Horizon` and freshness key |
| `stash/matching.py` | One regex per query word for the label, substring fallback on the payload, scoring, ranking with the freshness tiebreak |
| `stash/store.py` | The stashes folder: `default.txt` and the other files; load, append, comment out deleted lines; atomic, symlink-safe writes |
| `stash/snippets.py` | `{{name}}` and `{{name=default}}` placeholders, the reserved `date`, `time` and `clipboard`, filling |
| `stash/alfred.py` | Alfred Script Filter JSON: results and their copy/open/hand-off/fill/resolve action, stash and view rows, the *Run* and *Add* items, prompt rows, hints |
| `stash/cli.py` | Commands `search`, `add`, `delete`, `edit`, `open`, `alfred`, `prompt`, `resolve`, `fill`; the stamp on add, the view searches; workflow variables |
| `run.py` | Entry point Alfred calls |
| `make_plist.py` | Source of `info.plist`: keywords, the prompt filter, the router, connections, variables |
| `scripts/build.py`, `scripts/smoke.py`, `scripts/make_icons.py`, `scripts/make_gifs.py` | Build the bundle; run it the way Alfred would; draw `stash.png` (📒 on the icon's tile); draw the GIFs |
| `Makefile`, `.github/workflows/ci.yml` | The targets above, and CI that runs them |
| `tests/` | pytest suite, including a structural check of `info.plist` |
| `bench.py` | End-to-end latency benchmark |
| `examples/` | Sample folder: the stashes `default.txt` and `checklists.txt` |
| `docs/` | `MANUAL.md`, the typing scenarios, the stashes they run against, and the GIFs drawn from them in both schemes |
