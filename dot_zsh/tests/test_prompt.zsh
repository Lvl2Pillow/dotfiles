#!/usr/bin/env zsh
# Tests for the async prompt (only rendering — async setup requires ZLE)

source "${0:A:h}/../05_prompt.zsh" 2>/dev/null || source "${0:A:h}/../05_prompt.zsh.tmpl" 2>/dev/null

local tests=0 passed=0 failed=0

assert() {
  local actual="$1" expected="$2" name="$3"
  ((tests++))
  if [[ "$actual" == "$expected" ]]; then
    ((passed++))
  else
    echo "FAIL: $name"
    echo "  expected: '$expected'"
    echo "  got:      '$actual'"
    ((failed++))
  fi
}

setup_git_repo() {
  local dir="$1"
  git init -b main "$dir" >/dev/null 2>&1
  (
    cd "$dir"
    git config user.email test@test
    git config user.name test
    echo "init" > init
    git add init
    git commit -m init >/dev/null 2>&1
  )
}

# ===================================================================
# Group 1: _prompt_truncate_dir (8 tests)
# ===================================================================
echo "=== _prompt_truncate_dir ==="

# 1. short unchanged
_prompt_truncate_dir "foo" 10
assert "$_prompt_dir_out" "foo" "truncate_dir: short unchanged"

# 2. at cap (exactly 10 chars)
_prompt_truncate_dir "1234567890" 10
assert "$_prompt_dir_out" "1234567890" "truncate_dir: at cap"

# 3. truncated (11 chars, cap=10)
_prompt_truncate_dir "12345678901" 10
assert "$_prompt_dir_out" "12...78901" "truncate_dir: truncated"

# 4. root
_prompt_truncate_dir "/" 10
assert "$_prompt_dir_out" "/" "truncate_dir: root"

# 5. empty string
_prompt_truncate_dir "" 10
assert "$_prompt_dir_out" "" "truncate_dir: empty string"

# 6. single char
_prompt_truncate_dir "a" 10
assert "$_prompt_dir_out" "a" "truncate_dir: single char"

# 7. min cap=6
_prompt_truncate_dir "abcdefg" 6
assert "$_prompt_dir_out" "ab...g" "truncate_dir: min cap=6"

# 8. path with % chars
_prompt_truncate_dir "/tmp/50%off" 20
assert "$_prompt_dir_out" "/tmp/50%off" "truncate_dir: path with % chars"

# ===================================================================
# Group 2: _prompt_truncate_branch (7 tests)
# ===================================================================
echo "=== _prompt_truncate_branch ==="

# 1. short unchanged
_prompt_truncate_branch "main" 40
assert "$_prompt_branch_out" "main" "truncate_branch: short unchanged"

# 2. at cap
local b40="1234567890123456789012345678901234567890"
_prompt_truncate_branch "$b40" 40
assert "$_prompt_branch_out" "$b40" "truncate_branch: at cap"

# 3. truncated
_prompt_truncate_branch "very-long-feature-branch-name-for-testing-purposes" 40
assert "$_prompt_branch_out" "very-long-feature-branch-name-fo...poses" "truncate_branch: truncated"

# 4. min cap=8
_prompt_truncate_branch "123456789" 8
assert "$_prompt_branch_out" "...56789" "truncate_branch: min cap=8"

# 5. empty string
_prompt_truncate_branch "" 40
assert "$_prompt_branch_out" "" "truncate_branch: empty"

# 6. single char
_prompt_truncate_branch "a" 40
assert "$_prompt_branch_out" "a" "truncate_branch: single char"

# 7. branch with slashes
_prompt_truncate_branch "feature/some/branch" 40
assert "$_prompt_branch_out" "feature/some/branch" "truncate_branch: with slashes"

# ===================================================================
# Group 3: _prompt_precmd rendering with simulated async state
# ===================================================================
echo "=== _prompt_precmd rendering ==="

local TMPDIR
TMPDIR=$(mktemp -d /tmp/test_prompt_XXXXXX)
trap "rm -rf $TMPDIR" EXIT INT TERM

# Helper: cd to a real git repo (or bare dir), set async state, call precmd, popd
run_precmd() {
  local exit_code="$1" cols="$2" dir="$3" \
        staged="$4" unstaged="$5" result_pwd="$6"
  pushd -q "$dir"
  _prompt_git_staged=$staged
  _prompt_git_unstaged=$unstaged
  _prompt_git_result_pwd="$result_pwd"  # set to $dir to confirm async, empty for pending
  _prompt_git_checked_pwd="$dir"        # prevent triggering new async
  if [[ -n "$cols" ]]; then COLUMNS=$cols; else unset COLUMNS; fi
  (exit $exit_code)
  _prompt_precmd
  popd -q
}

# 1. No git repo, exit 0
local nogit="$TMPDIR/nogit"
mkdir -p "$nogit"
run_precmd 0 "" "$nogit" 0 0 ""
assert "$PROMPT" "%F{135}${nogit}%f %(#.#.%%)%f " "precmd: no repo, exit 0"

# 2. No git repo, exit 1
run_precmd 1 "" "$nogit" 0 0 ""
assert "$PROMPT" "%F{135}${nogit}%f %F{196}%(#.#.%%)%f " "precmd: no repo, exit 1"

# 3. Clean repo, exit 0 (green branch because result_pwd == $PWD)
local clean="$TMPDIR/clean"
setup_git_repo "$clean"
run_precmd 0 "" "$clean" 0 0 "$clean"
assert "$PROMPT" "%F{135}${clean}%f %F{076}main%f %(#.#.%%)%f " "precmd: clean, exit 0"

# 4. Clean repo, exit 1
run_precmd 1 "" "$clean" 0 0 "$clean"
assert "$PROMPT" "%F{135}${clean}%f %F{076}main%f %F{196}%(#.#.%%)%f " "precmd: clean, exit 1"

# 5. Staged changes only (blue)
run_precmd 0 "" "$clean" 1 0 "$clean"
assert "$PROMPT" "%F{135}${clean}%f %F{039}main%f %(#.#.%%)%f " "precmd: staged, blue"

# 6. Unstaged changes only (yellow — higher priority)
run_precmd 0 "" "$clean" 0 1 "$clean"
assert "$PROMPT" "%F{135}${clean}%f %F{178}main%f %(#.#.%%)%f " "precmd: unstaged, yellow"

# 7. Both staged and unstaged — unstaged wins (yellow)
run_precmd 0 "" "$clean" 1 1 "$clean"
assert "$PROMPT" "%F{135}${clean}%f %F{178}main%f %(#.#.%%)%f " "precmd: both, unstaged wins"

# 8. Detached HEAD
local detached_repo="$TMPDIR/detached"
setup_git_repo "$detached_repo"
pushd -q "$detached_repo"
local sha=$(git rev-parse HEAD)
git checkout "$sha" 2>/dev/null
_git_checkout_return=$?
run_precmd 0 "" "$detached_repo" 0 0 "$detached_repo"
local expected_detached_branch="@${sha:0:7}"
assert "$PROMPT" "%F{135}${detached_repo}%f %F{076}${expected_detached_branch}%f %(#.#.%%)%f " "precmd: detached HEAD"
git checkout main 2>/dev/null
popd -q

# 9. HOME ~ substitution (no git repo, no branch)
local home_dir="$TMPDIR/home_test"
mkdir -p "$home_dir/subdir"
local saved_home="$HOME"
HOME="$home_dir"
pushd -q "$home_dir/subdir"
_prompt_git_staged=0
_prompt_git_unstaged=0
_prompt_git_result_pwd=""
_prompt_git_checked_pwd="$PWD"
unset COLUMNS
(exit 0)
_prompt_precmd
assert "$PROMPT" "%F{135}~/subdir%f %(#.#.%%)%f " "precmd: HOME ~ substitution"
popd -q
HOME="$saved_home"

# 10. %-escaping in dir name (no git repo)
local percent_dir="$TMPDIR/d%p"
mkdir -p "$percent_dir"
run_precmd 0 "" "$percent_dir" 0 0 ""
local expected_dir="${TMPDIR}/d%%p"
assert "$PROMPT" "%F{135}${expected_dir}%f %(#.#.%%)%f " "precmd: %-escaping in dir name"

# 11. Wide terminal (COLUMNS=120, short branch, long dir) — extra goes to dir
local wide_dir="$TMPDIR/a_medium_length_directory_for_truncation_testing"
setup_git_repo "$wide_dir"
local dir_len=${#wide_dir}
if (( dir_len <= 36 )); then
  echo "SKIP: wide_dir too short (${dir_len} <= 36), test not meaningful"
else
  run_precmd 0 "120" "$wide_dir" 0 0 "$wide_dir"
  assert "$PROMPT" "%F{135}${wide_dir}%f %F{076}main%f %(#.#.%%)%f " "precmd: wide terminal"
fi

# 12. Tight terminal (COLUMNS=69, long branch) — branch truncated
local tight_dir="$TMPDIR/tight"
setup_git_repo "$tight_dir"
local long_branch="very-long-feature-branch-name-for-testing-purposes"
pushd -q "$tight_dir"
git checkout -b "$long_branch" 2>/dev/null
popd -q
run_precmd 0 "69" "$tight_dir" 0 0 "$tight_dir"
local expected_br="very-long-feature-branch-name-fo...poses"
assert "$PROMPT" "%F{135}${tight_dir}%f %F{076}${expected_br}%f %(#.#.%%)%f " "precmd: tight, branch truncated"

# 13. Root dir / (no git repo)
pushd -q /
_prompt_branch_out=""
_prompt_git_staged=0
_prompt_git_unstaged=0
_prompt_git_result_pwd=""
_prompt_git_checked_pwd="/"
unset COLUMNS
(exit 0)
_prompt_precmd
assert "$PROMPT" "%F{135}/%f %(#.#.%%)%f " "precmd: root dir /"
popd -q

# ===================================================================
# Group 4: Performance — rendering only, suppress everything async
# ===================================================================
echo "=== Performance ==="
local perf_iterations=1000
typeset -F SECONDS

# Disable git detection and async to measure rendering speed only
local _branch_save=$functions[_prompt_git_branch]
local _async_save=$functions[_prompt_async_git_start]
_prompt_git_branch() { _prompt_branch_out=""; return 1; }
_prompt_async_git_start() { :; }

# Performance test 1: no branch
local bench_dir="$TMPDIR/bench"
mkdir -p "$bench_dir"
pushd -q "$bench_dir"
_prompt_branch_out=""
_prompt_git_staged=0
_prompt_git_unstaged=0
typeset -F perf_start=$SECONDS
repeat $perf_iterations; do _prompt_precmd; done
typeset -F perf_elapsed=$(( SECONDS - perf_start ))
((tests++))
if (( perf_elapsed < 2.0 )); then
  echo "PASS: performance (no repo) took ${perf_elapsed}s"
  ((passed++))
else
  echo "FAIL: performance (no repo) took ${perf_elapsed}s"
  ((failed++))
fi
popd -q

# Switch to a branch-returning stub
_prompt_git_branch() { _prompt_branch_out="$long_branch"; return 0; }

# Performance test 2: with branch
pushd -q "$tight_dir"
_prompt_git_staged=0
_prompt_git_unstaged=0
typeset -F perf2_start=$SECONDS
repeat $perf_iterations; do _prompt_precmd; done
typeset -F perf2_elapsed=$(( SECONDS - perf2_start ))
((tests++))
if (( perf2_elapsed < 2.0 )); then
  echo "PASS: performance (with branch) took ${perf2_elapsed}s"
  ((passed++))
else
  echo "FAIL: performance (with branch) took ${perf2_elapsed}s"
  ((failed++))
fi
popd -q

# Restore
functions[_prompt_git_branch]=$_branch_save
functions[_prompt_async_git_start]=$_async_save

# ===================================================================
# Report
# ===================================================================
echo ""
echo "========================================"
if (( failed > 0 )); then
  echo "FAILED: $failed test(s) failed, $passed passed (out of $tests)"
  exit 1
else
  echo "All $passed tests passed!"
  exit 0
fi
