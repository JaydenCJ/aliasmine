# Contributing to aliasmine

Thanks for your interest in contributing. Issues, discussions, and pull
requests are all welcome.

## Development setup

```bash
git clone https://github.com/JaydenCJ/aliasmine
cd aliasmine
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running the checks

```bash
pytest                 # 93 offline unit/CLI tests
bash scripts/smoke.sh  # end-to-end: scan, suggest, export, error paths
```

Both must pass before a pull request is reviewed; the smoke script prints
`SMOKE OK` on success. Everything runs offline in well under a minute — no
API keys, no network, no real history files touched.

## Before you open a pull request

1. Format and lint if you have the tools (`ruff format` / `ruff check`); keep
   the style of the surrounding code either way.
2. `pytest` must pass.
3. `bash scripts/smoke.sh` must print `SMOKE OK`.
4. Add tests for behavior changes; keep logic in the pure modules
   (`history`, `normalize`, `mining`, `naming`, `existing`, `savings`) and
   out of `cli.py`.

## Ground rules

- **No new runtime dependencies.** The package is standard-library only;
  that is a feature. Test-only dependencies belong in the `dev` extra.
- **Never write to a user's files.** aliasmine reads history and rc files
  and prints; the only write is `export --out`, to a path the user named.
- **Determinism is part of the contract.** Same history in, same report
  out — no wall clock, no randomness, no locale-dependent output.
- **Keep the three READMEs aligned.** `README.md`, `README.zh.md`, and
  `README.ja.md` are line-for-line translations; update all three when you
  change one (English is the authoritative version).
- Code comments and doc comments are written in English.

## Reporting bugs

Please include `aliasmine --version`, the exact command line, and — if you
can share it — a minimal history snippet that reproduces the problem
(scrub anything sensitive first; a dozen lines is usually enough).

## Security

Please do not open public issues for security problems; use GitHub's
private vulnerability reporting on this repository instead.
