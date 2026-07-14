# aliasmine examples

Two synthetic-but-realistic history files and an rc-file snippet, so you can
try every subcommand without pointing the tool at your own dotfiles first.
Everything runs offline.

| File | What it is |
| --- | --- |
| `sample_zsh_history` | ~1,700 entries in zsh `EXTENDED_HISTORY` format — three months of a web developer's shell life, including `git status` typed 340 times |
| `sample_bash_history` | 52 entries in bash format with `HISTTIMEFORMAT` epoch comments |
| `sample_aliases.sh` | an rc-file snippet showing every alias dialect `--existing` understands |

## 1. The shareable report

```bash
aliasmine scan examples/sample_zsh_history
```

The headline at the bottom ("You typed `git status` 340 times…") is computed
from this file; your own history will produce your own confession.

## 2. Proposals, priced

```bash
aliasmine suggest examples/sample_zsh_history
aliasmine suggest examples/sample_zsh_history --json   # same data for scripts
```

## 3. Respecting what you already have

```bash
aliasmine suggest examples/sample_zsh_history --existing examples/sample_aliases.sh
```

`git status` disappears from the proposals (it is covered by `gs`), and the
scan report instead points out how often the expansion was still typed in
full — the alias you own but do not use.

## 4. Adopt the winners

```bash
aliasmine export examples/sample_zsh_history --format zsh   # alias lines
aliasmine export examples/sample_zsh_history --format fish  # abbr lines
```

Append the output to your rc file, reload the shell, and stop retyping.
