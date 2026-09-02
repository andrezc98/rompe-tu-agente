#!/usr/bin/env bash
# Fails if anything committed looks like an account id, ARN with account, access key, or a client name.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# ONE regex engine, everywhere: the system `grep -E` (POSIX ERE). Verified on this machine
# (Apple Git-155, git 2.50.1) that `git grep -E` silently treats `\b`, `\s`, `\S` as literal
# characters instead of the GNU/PCRE shorthands they look like -- a pattern using them matches
# under the system `grep -E` but NOT under `git grep -E`, with no error, just silent
# under-matching. So `git` is used only to enumerate files (`git ls-files`); every regex match
# happens via `scan_files()`, which always shells out to the system `grep`. Patterns below are
# therefore POSIX ERE only: no \b/\s/\S/\d, word boundaries are `(^|[^0-9])...([^0-9]|$)` style.
#
# aws_secret_access_key/OPENAI_API_KEY are value-shaped, not bare-name matches: a real AWS
# secret key is 40 base64-ish chars, so `aws_secret_access_key="y"` (test fixtures) and the
# literal kwarg name in agent/tools.py don't match, only an actual-looking value does.
# `phdata.io` stays: it's the speaker's public employer domain, not a secret.
#
# Client/codename literals do NOT live here (a guard containing the names it protects would
# publish them the moment this file is committed) -- see build_extra_pattern() below.
BASE_PATTERN='arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9]{12}:|(AKIA|ASIA)[0-9A-Z]{16}|aws_secret_access_key[[:space:]]*[=:][[:space:]]*["'\'']?[A-Za-z0-9/+]{40}|(^|[^0-9A-Fa-f.])[0-9]{12}([^0-9A-Fa-f.]|$)|phdata\.io|OPENAI_API_KEY=[^[:space:]]+'

# Appends word-list alternatives from an optional, git-ignored file: one bare word per line
# ('#'-comment and blank lines skipped). Each word is whitelisted (letters/digits/._- only) and
# wrapped as a boundary-safe alternative, so client names/codenames never sit in this tracked
# script as regex syntax, only as plain words in a file that is never committed. On a bad word,
# prints the required message and returns 2 (caller decides whether to exit); never matches
# silently wrong. File path: $SANITIZE_EXTRA, default .sanitize-extra at the repo root.
build_extra_pattern() {
  local file="${SANITIZE_EXTRA:-.sanitize-extra}" line pattern=""
  [[ -f "$file" ]] || { printf ''; return 0; }
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      ''|'#'*) continue ;;
    esac
    if ! grep -Eq '^[A-Za-z0-9._-]+$' <<<"$line"; then
      echo "sanitize-check: bad word in .sanitize-extra: $line" >&2
      return 2
    fi
    # ponytail: '.' in a word is left as "any char" (like the rest of BASE_PATTERN's dots
    # elsewhere use \. when an exact dot is meant); over-matching a word is the safe direction.
    if [[ -n "$pattern" ]]; then
      pattern="${pattern}|(^|[^[:alnum:]_])${line}([^[:alnum:]_]|\$)"
    else
      pattern="(^|[^[:alnum:]_])${line}([^[:alnum:]_]|\$)"
    fi
  done < "$file"
  printf '%s' "$pattern"
}

# Scans a file list against $1 (a POSIX ERE) with the system grep, case-insensitively.
# File list: $SANITIZE_FILES (newline-delimited manifest, for --selftest) if set, else
# `git ls-files` (tracked + untracked-but-not-ignored, i.e. exactly what's about to be
# committed or is already committed). Returns grep's own exit code untouched: 0 = matched,
# 1 = no match (normal, not an error), 2 = grep error (caller must fail closed on this).
scan_files() {
  local pattern="$1" f files=()
  if [[ -n "${SANITIZE_FILES:-}" ]]; then
    while IFS= read -r f; do
      [[ -n "$f" ]] && files+=("$f")
    done < "$SANITIZE_FILES"
  else
    while IFS= read -r -d '' f; do
      files+=("$f")
    done < <(git ls-files -z --cached --others --exclude-standard -- . ':!uv.lock' ':!demo/sanitize-check.sh')
  fi
  [[ ${#files[@]} -eq 0 ]] && return 1
  grep -EnHIi "$pattern" -- "${files[@]}"
}

# The 000000000000 test fixture must not hide a REAL id/secret on the same line: re-test each
# matching line with that placeholder blanked out, against the same pattern. A line whose only
# reason to match was the fake account no longer matches; a line with a real leak still does.
real_hits() {
  local pattern="$1" matches="$2"
  [[ -z "$matches" ]] && return 1
  printf '%s\n' "$matches" | sed 's/000000000000/FAKEACCT/g' | grep -E -i "$pattern"
}

selftest() {
  local fail=0 dir
  dir="$(mktemp -d)"
  trap 'rm -rf "$dir"' RETURN

  check_content() { # check_content <pattern> <expect: match|nomatch> <content> <label>
    local pattern="$1" expect="$2" content="$3" label="$4" f manifest got=nomatch
    f="$(mktemp "$dir/case.XXXXXX")"
    manifest="$(mktemp "$dir/manifest.XXXXXX")"
    printf '%s\n' "$content" > "$f"
    printf '%s\n' "$f" > "$manifest"
    SANITIZE_FILES="$manifest" scan_files "$pattern" >/dev/null && got=match
    if [[ "$got" == "$expect" ]]; then
      echo "ok   - $label"
    else
      echo "FAIL - $label (expected $expect, got $got)" >&2
      fail=1
    fi
  }

  check_content "$BASE_PATTERN" match   "123456789012"                    "12-digit account id matches"
  check_content "$BASE_PATTERN" nomatch "1234567890123"                   "13-digit number does not match"
  check_content "$BASE_PATTERN" nomatch '"span_id": "8d8b385763102690"'  "12 digits inside a hex span id do not match"
  check_content "$BASE_PATTERN" nomatch "3.519357654122E-4"               "12 digits inside a float mantissa do not match"
  check_content "$BASE_PATTERN" match   "Account: 123456789012"           "12-digit account id after a space matches"
  check_content "$BASE_PATTERN" match   "arn:aws:iam::123456789012:role/x" "arn with account id matches"
  check_content "$BASE_PATTERN" match   "AKIA1234567890ABCDEF"            "AKIA + 16 uppercase alnum matches"
  check_content "$BASE_PATTERN" nomatch 'aws_secret_access_key="y"'       "aws_secret_access_key with a short test fixture does not match"
  check_content "$BASE_PATTERN" match   "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" "aws_secret_access_key with a 40-char value matches"
  check_content "$BASE_PATTERN" nomatch "OPENAI_API_KEY="                 "OPENAI_API_KEY with no value does not match"
  check_content "$BASE_PATTERN" match   "OPENAI_API_KEY=sk-abc"           "OPENAI_API_KEY with a value matches"

  # Extra word list: only a throwaway fake word ("acme") ever appears here or in the script.
  local extra_file combined
  extra_file="$(mktemp "$dir/extra.XXXXXX")"
  printf '# comment, ignored\n\nacme\n' > "$extra_file"
  combined="$(SANITIZE_EXTRA="$extra_file" build_extra_pattern)"
  combined="${BASE_PATTERN}|${combined}"

  check_content "$combined" nomatch "basura" "loading the extra list does not affect unrelated words"
  check_content "$combined" match   "acme"   "extra list entry matches when the file is present"
  check_content "$combined" match   "Acme,"  "extra list entry matches case-insensitively with trailing punctuation"

  # Same-line leak: a fake account next to a real one must still be reported.
  local f manifest hits reported
  f="$(mktemp "$dir/case.XXXXXX")"
  manifest="$(mktemp "$dir/manifest.XXXXXX")"
  printf 'arn:aws:iam::000000000000:role/x and arn:aws:iam::111122223333:role/y\n' > "$f"
  printf '%s\n' "$f" > "$manifest"
  hits="$(SANITIZE_FILES="$manifest" scan_files "$BASE_PATTERN")" || true
  reported="$(real_hits "$BASE_PATTERN" "$hits")" || true
  if [[ -n "$reported" ]]; then
    echo "ok   - same-line leak (fake account next to a real one) is still reported"
  else
    echo "FAIL - same-line leak (fake account next to a real one) should be reported" >&2
    fail=1
  fi

  # Fake-account-only line must NOT be reported.
  f="$(mktemp "$dir/case.XXXXXX")"
  manifest="$(mktemp "$dir/manifest.XXXXXX")"
  printf 'arn:aws:iam::000000000000:role/x\n' > "$f"
  printf '%s\n' "$f" > "$manifest"
  hits="$(SANITIZE_FILES="$manifest" scan_files "$BASE_PATTERN")" || true
  reported="$(real_hits "$BASE_PATTERN" "$hits")" || true
  if [[ -z "$reported" ]]; then
    echo "ok   - fake-account-only line is not reported"
  else
    echo "FAIL - fake-account-only line should not be reported" >&2
    fail=1
  fi

  # A malformed extra word must make the whole script exit 2, fail closed.
  local bad_extra sub_rc=0
  bad_extra="$(mktemp "$dir/bad.XXXXXX")"
  printf 'a(b\n' > "$bad_extra"
  SANITIZE_EXTRA="$bad_extra" bash demo/sanitize-check.sh >/dev/null 2>&1 || sub_rc=$?
  if [[ "$sub_rc" -eq 2 ]]; then
    echo "ok   - malformed extra word makes the script exit 2"
  else
    echo "FAIL - malformed extra word should make the script exit 2 (got $sub_rc)" >&2
    fail=1
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

# No exclusions beyond this script and the lockfile (they're built into scan_files()'s file
# list). Build the extra pattern first so a malformed .sanitize-extra fails fast, before any
# scanning; every fallible grep-backed call below captures its exit code explicitly so a real
# grep error (2) always becomes `exit 2`, never a silently-passed check.
rc=0
extra="$(build_extra_pattern)" || rc=$?
if [[ "$rc" -eq 2 ]]; then
  exit 2
fi
FULL="$BASE_PATTERN"
[[ -n "$extra" ]] && FULL="${FULL}|${extra}"

rc=0
matches="$(scan_files "$FULL")" || rc=$?
if [[ "$rc" -eq 2 ]]; then
  echo "sanitize-check: grep error while scanning" >&2
  exit 2
fi

if [[ -n "$matches" ]]; then
  rc=0
  real="$(real_hits "$FULL" "$matches")" || rc=$?
  if [[ "$rc" -eq 2 ]]; then
    echo "sanitize-check: grep error while re-checking matches" >&2
    exit 2
  fi
  if [[ -n "$real" ]]; then
    printf '%s\n' "$real"
    echo "sanitize-check: FOUND sensitive-looking strings above" >&2
    exit 1
  fi
fi
echo "sanitize-check: clean"
