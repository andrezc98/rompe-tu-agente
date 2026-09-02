#!/usr/bin/env bash
# Fails if anything committed looks like an account id, ARN with account, access key, or a client name.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Verified on this machine: `\b` works as a real word boundary under both BSD grep (`grep -E`,
# the tool the --selftest below actually runs) and git's built-in grep (`git grep -E`), so the
# PCRE (-P) fallback the brief anticipated for macOS was not needed here. Ran with plain `-E`:
# `123456789012` matches, `1234567890123` does not, `basura`/`mensura` don't, `sura` alone does.
PATTERN='arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9]{12}:|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|aws_secret_access_key|\b[0-9]{12}\b|\bsura\b|morrisopazo|phdata\.io|bedrock-api-key-|OPENAI_API_KEY='

selftest() {
  local matches fail=0

  # One heredoc through the exact PATTERN above, then assert which lines came back.
  matches="$(grep -E "$PATTERN" <<'LINES' || true
123456789012
1234567890123
basura
mensura
sura
arn:aws:iam::123456789012:role/x
AKIA1234567890ABCDEF
LINES
)"

  assert() { # assert <expect: match|nomatch> <line> <label>
    local expect="$1" line="$2" label="$3" got=nomatch
    grep -qxF "$line" <<<"$matches" && got=match
    if [[ "$got" == "$expect" ]]; then
      echo "ok   - $label"
    else
      echo "FAIL - $label (expected $expect, got $got)" >&2
      fail=1
    fi
  }

  assert match   "123456789012"                          "12-digit account id matches"
  assert nomatch "1234567890123"                          "13-digit number does not match"
  assert nomatch "basura"                                 "basura does not match"
  assert nomatch "mensura"                                "mensura does not match"
  assert match   "sura"                                   "sura alone matches"
  assert match   "arn:aws:iam::123456789012:role/x"       "arn with account id matches"
  assert match   "AKIA1234567890ABCDEF"                   "AKIA + 16 uppercase alnum matches"

  # The fake account used across tests/test_tools.py (000000000000 is not a real AWS account
  # id) must be excluded from the real check below via `grep -v 000000000000`.
  local fake="arn:aws:iam::000000000000:role/aws-cdarg-sentinel-role-agent-demo"
  if echo "$fake" | grep -E "$PATTERN" | grep -v '000000000000' | grep -q .; then
    echo "FAIL - fake test account 000000000000 should be excluded from the real check" >&2
    fail=1
  else
    echo "ok   - fake test account 000000000000 excluded"
  fi

  if [[ "$fail" -eq 0 ]]; then
    echo "sanitize-check --selftest: all assertions passed"
  else
    echo "sanitize-check --selftest: FAILED" >&2
  fi
  return "$fail"
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  exit $?
fi

# Exclusions beyond this script and the lockfile:
#   - docs/** carries the project's plan/spec write-up, which quotes this very PATTERN string
#     (including the literal substrings below) and dummy boto3 kwargs as documentation, not
#     committed secrets.
#   - agent/tools.py, tests/test_config.py, tests/test_tools.py use the literal boto3 kwarg
#     name `aws_secret_access_key` (with STS-vended values, never a hardcoded key) and the
#     synthetic `bedrock-api-key-` test prefix — real code/tests, not leaked material.
# --untracked: this runs before a commit, i.e. exactly when new results/assets are still
# unstaged; without it git grep would only see already-tracked files and miss them entirely.
# It still respects .gitignore, so .superpowers/ (git-ignored) is not scanned either way.
if git grep --untracked -nEi "$PATTERN" -- \
    ':!demo/sanitize-check.sh' ':!uv.lock' ':!docs/**' \
    ':!agent/tools.py' ':!tests/test_config.py' ':!tests/test_tools.py' \
  | grep -v '000000000000'; then
  echo "sanitize-check: FOUND sensitive-looking strings above" >&2
  exit 1
fi
echo "sanitize-check: clean"
