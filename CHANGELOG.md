# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-13

### Added

- History readers for bash (plain and `HISTTIMEFORMAT` epoch comments),
  zsh (`EXTENDED_HISTORY` with multi-line stitching and metafied-byte
  decoding, plus plain fallback), and fish (`- cmd:` / `when:` format with
  escape handling). Format auto-detection per file; `--shell` to force one.
- Shell-aware tokenizer that survives unterminated quotes and keeps token
  text verbatim, so proposed aliases expand to exactly what was typed.
- Frequency mining of exact commands *and* token-prefix stems
  (`git commit -m` with varying messages), with a dominant-child rule that
  proposes the longer form when a stem almost always continues the same way.
- Deterministic alias-name generation (initials with option letters,
  single-token prefix walks) checked against a curated common-command list,
  every program seen in the mined history, and the user's existing aliases.
- Existing-alias awareness: parses bash/zsh `alias`, fish `alias`, and fish
  `abbr` lines out of any rc file; covered commands are not re-suggested,
  and aliases whose expansion is still typed in full are called out.
- Savings accounting: exact keystroke counts per alias and in total, an
  overlap-charging rule so stem/child suggestions never double-count a
  keystroke, and a WPM-based time estimate (`--wpm`).
- CLI: `scan` (shareable report with proportional bars), `suggest`
  (priced proposals), `export` (`bash`/`zsh` alias lines or fish `abbr`
  definitions, correctly quoted), `stats` (corpus numbers); `--json` on
  scan/suggest/stats; `--color auto|always|never` honoring `NO_COLOR`.
- Bundled sample histories and an rc-file example under `examples/`.
- 93 offline pytest tests and `scripts/smoke.sh` (prints `SMOKE OK`).

### Notes

- The repository ships no CI workflow; verification is local — `pip install -e '.[dev]' && pytest && bash scripts/smoke.sh`.

[0.1.0]: https://github.com/JaydenCJ/aliasmine/releases/tag/v0.1.0
