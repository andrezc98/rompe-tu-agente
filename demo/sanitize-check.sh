#!/usr/bin/env bash
# Fails if anything committed looks like an account id, ARN with account, access key, or a client name.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Verified on this machine: `\b` works as a real word boundary under both BSD grep (`grep -E`,
# the tool the --selftest below actually runs) and git's built-in grep (`git grep -E`), so the
# PCRE (-P) fallback the brief anticipated for macOS was not needed here. Proven via the
# `\b[0-9]{12}\b` assertions below (12 digits match, 13 don't).
#
# aws_secret_access_key/OPENAI_API_KEY are value-shaped, not bare-name matches: a real AWS
# secret key is 40 base64-ish chars, so `aws_secret_access_key="y"` (test fixtures) and the
# literal kwarg name in agent/tools.py no longer match, only an actual-looking value does.
# `bedrock-api-key-` was dropped: it only ever matched our own synthetic test prefix.
# `phdata.io` stays: it's the speaker's public employer domain, not a secret.
#
# Client/codename literals do NOT live here (a guard that contains the names it protects would
# publish them the moment this file is committed). They go in an optional, git-ignored word
# list instead — see full_pattern() below.
PATTERN="arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9]{12}:|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|aws_secret_access_key\s*[=:]\s*[\"']?[A-Za-z0-9/+]{40}|\b[0-9]{12}\b|phdata\.io|OPENAI_API_KEY=\S+"

# Appends non-comment, non-blank lines of an optional word list to PATTERN. One extended-regex
# alternative per line; '#'-prefixed and blank lines are skipped. File path is
# $SANITIZE_EXTRA or, by default, .sanitize-extra at the repo root (gitignored, never committed).
full_pattern() {
  local file="${SANITIZE_EXTRA:-.sanitize-extra}" extra
  if [[ -f "$file" ]]; then
    extra="$(grep -vE '^[[:space:]]*(#|$)' "$file" | paste -sd '|' -)"
    if [[ -n "$extra" ]]; then
      printf '%s|%s' "$PATTERN" "$extra"
      return
    fi
  fi
  printf '%s' "$PATTERN"
}

selftest() {
  local matches fail=0

  # One heredoc through the exact PATTERN above, then assert which lines came back.
  matches="$(grep -E "$PATTERN" <<'LINES' || true
123456789012
1234567890123
basura
mensura
arn:aws:iam::123456789012:role/x
AKIA1234567890ABCDEF
aws_secret_access_key="y"
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
bedrock-api-key-us-east-1
OPENAI_API_KEY=
OPENAI_API_KEY=sk-abc
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
  assert match   "arn:aws:iam::123456789012:role/x"       "arn with account id matches"
  assert match   "AKIA1234567890ABCDEF"                   "AKIA + 16 uppercase alnum matches"
  assert nomatch 'aws_secret_access_key="y"'               "aws_secret_access_key with a short test fixture does not match"
  assert match   "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" "aws_secret_access_key with a 40-char value matches"
  assert nomatch "bedrock-api-key-us-east-1"               "bedrock-api-key- test fixture does not match"
  assert nomatch "OPENAI_API_KEY="                         "OPENAI_API_KEY with no value does not match"
  assert match   "OPENAI_API_KEY=sk-abc"                   "OPENAI_API_KEY with a value matches"

  # The fake account used across tests/test_tools.py (000000000000 is not a real AWS account
  # id) must be excluded from the real check below via `grep -v 000000000000`.
  local fake="arn:aws:iam::000000000000:role/aws-cdarg-sentinel-role-agent-demo"
  if echo "$fake" | grep -E "$PATTERN" | grep -v '000000000000' | grep -q .; then
    echo "FAIL - fake test account 000000000000 should be excluded from the real check" >&2
    fail=1
  else
    echo "ok   - fake test account 000000000000 excluded"
  fi

  # Optional word list mechanism: client/codename patterns never appear in this script or in
  # this test, only a throwaway fake word does, in a temp file passed via SANITIZE_EXTRA.
  local extra_tmp with_extra without_extra
  extra_tmp="$(mktemp)"
  trap 'rm -f "$extra_tmp"' RETURN
  printf '# comment line, ignored\n\n\\bacme\\b\n' > "$extra_tmp"

  with_extra="$(grep -E "$(SANITIZE_EXTRA="$extra_tmp" full_pattern)" <<'LINES' || true
basura
acme
LINES
)"
  without_extra="$(grep -E "$(SANITIZE_EXTRA=/no/such/file full_pattern)" <<'LINES' || true
basura
acme
LINES
)"

  if echo "$with_extra" | grep -qxF "basura"; then
    echo "FAIL - loading the extra list must not affect unrelated words" >&2
    fail=1
  else
    echo "ok   - loading the extra list does not affect unrelated words"
  fi
  if echo "$with_extra" | grep -qxF "acme"; then
    echo "ok   - extra list entry matches when the file is present"
  else
    echo "FAIL - extra list entry should match when the file is present" >&2
    fail=1
  fi
  if echo "$without_extra" | grep -qxF "acme"; then
    echo "FAIL - extra word should not match without the extra file" >&2
    fail=1
  else
    echo "ok   - extra word does not match without the extra file"
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

# No exclusions beyond this script and the lockfile: the patterns above are value-shaped
# (see the comment on PATTERN), so real source/test/doc files no longer need a pathspec carve-out.
# --untracked: this runs before a commit, i.e. exactly when new results/assets are still
# unstaged; without it git grep would only see already-tracked files and miss them entirely.
# It still respects .gitignore, so .superpowers/ (git-ignored) is not scanned either way.
if git grep --untracked -nEi "$(full_pattern)" -- ':!demo/sanitize-check.sh' ':!uv.lock' \
  | grep -v '000000000000'; then
  echo "sanitize-check: FOUND sensitive-looking strings above" >&2
  exit 1
fi
echo "sanitize-check: clean"
