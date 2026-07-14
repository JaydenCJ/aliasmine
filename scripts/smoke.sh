#!/usr/bin/env bash
# Smoke test for aliasmine: mine the bundled sample histories end-to-end,
# check the headline numbers, the proposals, the export formats, and the
# error path. Self-contained: pure stdlib, no network, idempotent.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

# Zero runtime dependencies: running from src/ needs no install.
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/aliasmine-smoke.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

echo "[smoke] python: $("$PYTHON" --version 2>&1)"

# 1. scan: the shareable report on the bundled zsh sample.
scan_out="$("$PYTHON" -m aliasmine scan "$ROOT/examples/sample_zsh_history" --color never)" \
  || fail "scan exited non-zero"
echo "$scan_out" | sed -n '1p;20,22p' | sed 's/^/[scan] /'
echo "$scan_out" | grep -q "mined 1,694 history entries" || fail "scan entry count wrong"
echo "$scan_out" | grep -q 'You typed `git status` 340 times' || fail "scan headline missing"
echo "$scan_out" | grep -q 'Alias `gs` would have saved 2,720' || fail "scan savings wrong"

# 2. suggest: proposals are named, priced, and totalled.
suggest_out="$("$PYTHON" -m aliasmine suggest "$ROOT/examples/sample_zsh_history" --color never)"
echo "$suggest_out" | grep -Eq 'gs +git status +340 +8 +2,720' || fail "suggest missing gs row"
echo "$suggest_out" | grep -q "keystrokes saved" || fail "suggest missing total line"

# 3. suggest --json: machine output round-trips and self-checks.
"$PYTHON" -m aliasmine suggest "$ROOT/examples/sample_zsh_history" --json > "$WORKDIR/suggest.json"
"$PYTHON" - "$WORKDIR/suggest.json" <<'PYEOF' || fail "suggest --json inconsistent"
import json, sys
data = json.load(open(sys.argv[1]))
assert data["total_saved"] == sum(s["total_saved"] for s in data["suggestions"])
assert any(s["alias"] == "gs" and s["command"] == "git status" for s in data["suggestions"])
PYEOF

# 4. --existing: covered commands are not re-suggested; the guilt trip appears.
existing_out="$("$PYTHON" -m aliasmine suggest "$ROOT/examples/sample_zsh_history" \
  --existing "$ROOT/examples/sample_aliases.sh" --color never)"
echo "$existing_out" | grep -q 'git status' && fail "covered command was re-suggested"
scan_existing="$("$PYTHON" -m aliasmine scan "$ROOT/examples/sample_zsh_history" \
  --existing "$ROOT/examples/sample_aliases.sh" --color never)"
echo "$scan_existing" | grep -q 'You own alias `gs`' || fail "ignored-alias section missing"

# 5. export: zsh alias lines and fish abbr lines, written to a file.
"$PYTHON" -m aliasmine export "$ROOT/examples/sample_zsh_history" --format zsh \
  --out "$WORKDIR/aliases.zsh" >/dev/null
grep -q "alias gs='git status'" "$WORKDIR/aliases.zsh" || fail "zsh export missing alias"
fish_out="$("$PYTHON" -m aliasmine export "$ROOT/examples/sample_zsh_history" --format fish)"
echo "$fish_out" | grep -q "abbr -a gs 'git status'" || fail "fish export missing abbr"

# 6. the exported file is real shell: source it and use an alias.
bash_check="$(bash -c "shopt -s expand_aliases; source '$WORKDIR/aliases.zsh'; alias gs")"
echo "$bash_check" | grep -q "git status" || fail "exported alias not sourceable"

# 7. bash-format sample with HISTTIMEFORMAT comments parses too.
stats_out="$("$PYTHON" -m aliasmine stats "$ROOT/examples/sample_bash_history" --json)"
echo "$stats_out" | grep -q '"entries": 52' || fail "bash sample entry count wrong"

# 8. error path: a missing file fails cleanly with exit 1.
set +e
"$PYTHON" -m aliasmine scan "$WORKDIR/no-such-history" 2>"$WORKDIR/err.txt"
rc=$?
set -e
[ "$rc" -eq 1 ] || fail "missing file should exit 1, got $rc"
grep -q "history file not found" "$WORKDIR/err.txt" || fail "missing-file error text wrong"

# 9. --version agrees with the package.
version_out="$("$PYTHON" -m aliasmine --version)"
pkg_version="$("$PYTHON" -c 'import aliasmine; print(aliasmine.__version__)')"
[ "$version_out" = "aliasmine $pkg_version" ] \
  || fail "--version mismatch: '$version_out' vs package '$pkg_version'"

echo "SMOKE OK"
