# How aliasmine mines

This document pins down the algorithm so the numbers in a report can be
reproduced by hand. Everything below is deterministic: the same history
always produces the same report.

## 1. Parsing and normalization

Each history file is read leniently (zsh metafied bytes are decoded, junk
lines are kept as commands rather than crashing the parse) and every entry
is normalized: tokens are split on unquoted whitespace with quotes and
escapes preserved verbatim, then re-joined with single spaces. So
`git   status` and `git status` are one habit, but the message in
`git commit -m "fix"` keeps its exact quoting.

Lines that can never become aliases are dropped before counting: comments,
history expansions (`!!`, `!123`), and lines whose first token has no
alphanumeric characters.

## 2. Candidate generation

For every normalized command with tokens `t1 … tn`, every token-prefix
`t1 … tk` (k = 1…n) is counted. A prefix becomes a **candidate** when:

- it occurred at least `--min-count` times (default 5), and
- its text is at least `--min-length` characters (default 6).

A candidate is **exact** when every occurrence was the full command, and a
**prefix** (rendered with a trailing `+` in reports) when tails varied.

## 3. The dominant-child rule

A stem is dropped when a single one-token extension accounts for at least
90 % of its uses. If every `docker compose` you typed was
`docker compose up -d`, aliasing the stem would still leave you typing
`up -d` — so the longer command is proposed instead. Stems with diverse
tails (`kubectl get pods` / `kubectl get services`) survive alongside
their children.

## 4. Ranking

Candidates are ordered by *savings potential* — `count × (length − 2)`,
i.e. keystrokes reclaimable assuming a two-character alias — with ties
broken by count, then command text.

## 5. Naming

Names are generated deterministically: initials for multi-token commands
(`git status` → `gs`, options contribute a letter: `git commit -m` →
`gcm`), prefix walks for single tokens (`kubectl` → `k`, `ku`, …). A name
is rejected if it appears in the curated common-command list, names any
program seen in your own history, collides with an existing alias, or
fails to save at least 2 characters per use; rejection falls through to
progressively longer variants.

## 6. Pricing

Each suggestion is priced at `count × (len(command) − len(alias))`
keystrokes. When both a stem and a more specific child are suggested
(`npm run` and `npm run dev`), the child's uses are charged to the child
only; a stem whose every use is covered by children prices at zero and is
dropped. The grand total therefore never counts a keystroke twice. Time
estimates divide keystrokes by a typing speed of `--wpm` (default 60,
i.e. 5 characters per second) — an estimate, and labelled as such.

The scan header's *keystrokes on repeats* follows the same rule: each
occurrence is charged to the most specific surviving candidate that covers
it, so the headline can never exceed the corpus total reported by `stats`.
The per-row keystroke column, by contrast, is each candidate's own
`count × length` — raw evidence, so overlapping rows may overlap there.
