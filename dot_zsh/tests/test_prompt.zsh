#!/usr/bin/env zsh

source "${0:h}/../05_prompt.zsh"

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

reset_globals() {
  _prompt_is_git_cache=0
  _prompt_git_dir_cache=""
  _prompt_dir_cache=""
  _prompt_branch_out=""
  _prompt_dir_out=""
}

# --- temp directory ---
local TMPDIR
TMPDIR=$(mktemp -d /tmp/test_prompt_XXXXXX)
trap "rm -rf $TMPDIR" EXIT INT TERM

# ===================================================================
# Group 1: _prompt_truncate_dir (8 tests)
# ===================================================================
echo "=== _prompt_truncate_dir ==="

# 1. short unchanged
reset_globals
_prompt_truncate_dir "foo" 10
assert "$_prompt_dir_out" "foo" "truncate_dir: short unchanged"

# 2. at cap (exactly 10 chars)
reset_globals
_prompt_truncate_dir "1234567890" 10
assert "$_prompt_dir_out" "1234567890" "truncate_dir: at cap"

# 3. truncated (11 chars, cap=10 -> first 2 + ... + last 5)
#    "12345678901": first 2 = "12", ending_len=10-5=5, last 5 = "78901"
#    result: "12...78901" (10 chars)
reset_globals
_prompt_truncate_dir "12345678901" 10
assert "$_prompt_dir_out" "12...78901" "truncate_dir: truncated"

# 4. root
reset_globals
_prompt_truncate_dir "/" 10
assert "$_prompt_dir_out" "/" "truncate_dir: root"

# 5. empty string
reset_globals
_prompt_truncate_dir "" 10
assert "$_prompt_dir_out" "" "truncate_dir: empty string"

# 6. single char
reset_globals
_prompt_truncate_dir "a" 10
assert "$_prompt_dir_out" "a" "truncate_dir: single char"

# 7. min cap=6: "abcdefg" (7 chars), cap=6
#    first 2 = "ab", ending_len=6-5=1, last 1 = "g"
#    result: "ab...g" (6 chars)
reset_globals
_prompt_truncate_dir "abcdefg" 6
assert "$_prompt_dir_out" "ab...g" "truncate_dir: min cap=6"

# 8. path with % chars (under cap, % passed through literally)
reset_globals
_prompt_truncate_dir "/tmp/50%off" 20
assert "$_prompt_dir_out" "/tmp/50%off" "truncate_dir: path with % chars"

# ===================================================================
# Group 2: _prompt_truncate_branch (7 tests)
# ===================================================================
echo "=== _prompt_truncate_branch ==="

# 1. short unchanged
reset_globals
_prompt_truncate_branch "main" 40
assert "$_prompt_branch_out" "main" "truncate_branch: short unchanged"

# 2. at cap (exactly 40 chars)
reset_globals
local b40="1234567890123456789012345678901234567890"
_prompt_truncate_branch "$b40" 40
assert "$_prompt_branch_out" "$b40" "truncate_branch: at cap"

# 3. truncated (50 chars, cap=40)
#    "very-long-feature-branch-name-for-testing-purposes" = 50 chars
#    cap=40: beginning_len=40-8=32, first 32 chars, last 5
#    first 32: "very-long-feature-branch-name-fo"
#    last 5: "poses"
#    result: "very-long-feature-branch-name-fo...poses"
reset_globals
_prompt_truncate_branch "very-long-feature-branch-name-for-testing-purposes" 40
assert "$_prompt_branch_out" "very-long-feature-branch-name-fo...poses" "truncate_branch: truncated"

# 4. min cap=8: "123456789" (9 chars), cap=8
#    beginning_len=8-8=0, beginning="" (empty)
#    ending = last 5 = "56789"
#    result: "...56789"
reset_globals
_prompt_truncate_branch "123456789" 8
assert "$_prompt_branch_out" "...56789" "truncate_branch: min cap=8"

# 5. empty string
reset_globals
_prompt_truncate_branch "" 40
assert "$_prompt_branch_out" "" "truncate_branch: empty"

# 6. single char
reset_globals
_prompt_truncate_branch "a" 40
assert "$_prompt_branch_out" "a" "truncate_branch: single char"

# 7. branch with slashes (under cap, passed through unchanged)
reset_globals
_prompt_truncate_branch "feature/some/branch" 40
assert "$_prompt_branch_out" "feature/some/branch" "truncate_branch: with slashes"

# ===================================================================
# Group 3: _prompt_find_git (9 tests)
# ===================================================================
echo "=== _prompt_find_git ==="

# 1. .git dir in PWD
local find_git_1="$TMPDIR/find_git_1"
setup_git_repo "$find_git_1"
pushd -q "$find_git_1"
reset_globals
_prompt_find_git
local ret=$?
assert "$ret" "0" "find_git: .git dir in PWD (return)"
assert "$_prompt_git_dir_cache" "$find_git_1/.git" "find_git: .git dir in PWD (cache)"
popd -q

# 2. cache hit (same dir, second call returns immediately)
pushd -q "$find_git_1"
reset_globals
_prompt_find_git  # first call walks and caches
local ret1=$?
_prompt_find_git  # second call hits cache
local ret2=$?
assert "$ret1" "0" "find_git: cache hit first call"
assert "$ret2" "0" "find_git: cache hit second call"
popd -q

# 3. stale cache (HEAD removed -> detects stale, re-walks, re-caches)
pushd -q "$find_git_1"
reset_globals
_prompt_find_git  # prime cache
rm "$find_git_1/.git/HEAD"
_prompt_find_git  # should detect stale HEAD, invalidate, re-walk, find .git dir
local ret3=$?
assert "$ret3" "0" "find_git: stale cache recovers (return)"
assert "$_prompt_git_dir_cache" "$find_git_1/.git" "find_git: stale cache recovers (cache)"
# restore HEAD for later tests
echo "ref: refs/heads/main" > "$find_git_1/.git/HEAD"
popd -q

# 4. no .git returns 1
local nogit_dir="$TMPDIR/nogit"
mkdir -p "$nogit_dir"
pushd -q "$nogit_dir"
reset_globals
_prompt_find_git
local ret4=$?
assert "$ret4" "1" "find_git: no .git returns 1"
popd -q

# 5. non-git cache hit returns 1 (negative cache)
pushd -q "$nogit_dir"
reset_globals
_prompt_find_git  # walks up to root, finds nothing, caches negative
local ret5a=$?
_prompt_find_git  # cache hit, returns 1 immediately
local ret5b=$?
assert "$ret5a" "1" "find_git: non-git first call"
assert "$ret5b" "1" "find_git: non-git cache hit"
assert "$_prompt_is_git_cache" "0" "find_git: non-git cache flag"
popd -q

# 6. submodule .git file with gitdir:
local real_repo="$TMPDIR/real_repo"
setup_git_repo "$real_repo"
local submodule_dir="$TMPDIR/submodule"
mkdir -p "$submodule_dir"
echo "gitdir: $real_repo/.git" > "$submodule_dir/.git"
pushd -q "$submodule_dir"
reset_globals
_prompt_find_git
local ret6=$?
assert "$ret6" "0" "find_git: submodule .git file (return)"
assert "$_prompt_git_dir_cache" "$real_repo/.git" "find_git: submodule cache path"
popd -q

# 7. invalid .git file (garbage, not gitdir: format)
local invalid_dir="$TMPDIR/invalid_git"
mkdir -p "$invalid_dir"
echo "garbage content" > "$invalid_dir/.git"
pushd -q "$invalid_dir"
reset_globals
_prompt_find_git
local ret7=$?
assert "$ret7" "1" "find_git: invalid .git file"
popd -q

# 8. parent dir traversal (.git in parent directory)
local parent_repo="$TMPDIR/parent_repo"
setup_git_repo "$parent_repo"
mkdir -p "$parent_repo/subdir/deep"
pushd -q "$parent_repo/subdir/deep"
reset_globals
_prompt_find_git
local ret8=$?
assert "$ret8" "0" "find_git: parent dir traversal (return)"
assert "$_prompt_git_dir_cache" "$parent_repo/.git" "find_git: parent dir traversal (cache)"
popd -q

# 9. .git file with gitdir: pointing to non-existent directory
local bad_submodule="$TMPDIR/bad_submodule"
mkdir -p "$bad_submodule"
echo "gitdir: /nonexistent/path/to/git" > "$bad_submodule/.git"
pushd -q "$bad_submodule"
reset_globals
_prompt_find_git
local ret9=$?
assert "$ret9" "1" "find_git: gitdir points to non-existent dir"
popd -q

# ===================================================================
# Group 4: _prompt_git_branch (3 tests)
# ===================================================================
echo "=== _prompt_git_branch ==="

# 1. normal branch -> "main"
local branch_repo="$TMPDIR/branch_repo"
setup_git_repo "$branch_repo"
pushd -q "$branch_repo"
reset_globals
_prompt_git_branch
local gb_ret=$?
assert "$gb_ret" "0" "git_branch: normal branch (return)"
assert "$_prompt_branch_out" "main" "git_branch: normal branch (value)"
popd -q

# 2. detached HEAD -> @sha7
pushd -q "$branch_repo"
local sha=$(git rev-parse HEAD)
git checkout "$sha" 2>/dev/null
reset_globals
_prompt_git_branch
local gb_ret2=$?
local expected="@${sha:0:7}"
assert "$gb_ret2" "0" "git_branch: detached HEAD (return)"
assert "$_prompt_branch_out" "$expected" "git_branch: detached HEAD (value)"
# restore main branch
git checkout main 2>/dev/null
popd -q

# 3. no git dir -> "" + return 1
pushd -q "$nogit_dir"
reset_globals
_prompt_git_branch
local gb_ret3=$?
assert "$gb_ret3" "1" "git_branch: no git (return)"
assert "$_prompt_branch_out" "" "git_branch: no git (branch_out)"
popd -q

# ===================================================================
# Group 5: _prompt_precmd (10 tests)
# ===================================================================
echo "=== _prompt_precmd ==="

# Helper: call _prompt_precmd with given exit code and optional COLUMNS.
# Saves/restores PWD so subsequent tests aren't affected.
run_precmd() {
  local exit_code="$1"
  local columns="$2"
  local dir="$3"

  pushd -q "$dir"
  reset_globals
  if [[ -n "$columns" ]]; then
    COLUMNS="$columns"
  else
    unset COLUMNS
  fi

  if (( exit_code == 0 )); then
    :
  else
    (exit $exit_code)
  fi
  _prompt_precmd
  popd -q
}

# 1. No git dir, exit 0
run_precmd 0 "" "$nogit_dir"
assert "$PROMPT" "%F{135}${nogit_dir}%f %(#.#.%%)%f " "precmd: no git, exit 0"

# 2. No git dir, exit 1
run_precmd 1 "" "$nogit_dir"
assert "$PROMPT" "%F{135}${nogit_dir}%f %F{196}%(#.#.%%)%f " "precmd: no git, exit 1"

# 3. Git dir with branch, exit 0
local prompt_git="$TMPDIR/prompt_git"
setup_git_repo "$prompt_git"
run_precmd 0 "" "$prompt_git"
assert "$PROMPT" "%F{135}${prompt_git}%f %F{39}main%f %(#.#.%%)%f " "precmd: git branch, exit 0"

# 4. Git dir with branch, exit 1
run_precmd 1 "" "$prompt_git"
assert "$PROMPT" "%F{135}${prompt_git}%f %F{39}main%f %F{196}%(#.#.%%)%f " "precmd: git branch, exit 1"

# 5. HOME ~ substitution
local home_dir="$TMPDIR/home_test"
mkdir -p "$home_dir/subdir"
local saved_home="$HOME"
HOME="$home_dir"
pushd -q "$home_dir/subdir"
reset_globals
unset COLUMNS
:
_prompt_precmd
assert "$PROMPT" "%F{135}~/subdir%f %(#.#.%%)%f " "precmd: HOME ~ substitution"
popd -q
HOME="$saved_home"

# 6. %-escaping in dir name
#    Use a short path (<36 chars) to avoid truncation interfering with the % test
local percent_dir="$TMPDIR/d%p"
mkdir -p "$percent_dir"
run_precmd 0 "" "$percent_dir"
# The path d%p has one % literal which becomes %% in the prompt
local expected_dir="${TMPDIR}/d%%p"
assert "$PROMPT" "%F{135}${expected_dir}%f %(#.#.%%)%f " "precmd: %-escaping in dir name"

# 7. Wide terminal (COLUMNS=120, short branch, long dir) — extra goes to dir
#    extra = 40, branch "main" (4 chars) uses 0 extra, dir_cap = 36+40 = 76
#    Create a dir between 36 and 76 chars so it fits only with extra space
local wide_dir="$TMPDIR/a_medium_length_directory_for_truncation_testing"
rmdir "$wide_dir" 2>/dev/null; mkdir -p "$wide_dir"  # ensure fresh
setup_git_repo "$wide_dir"  # has main branch
local dir_len=${#wide_dir}
if (( dir_len <= 36 )); then
  echo "SKIP: wide_dir too short (${dir_len} <= 36), test not meaningful"
else
  run_precmd 0 "120" "$wide_dir"
  # With COLUMNS=120: dir_cap=76, branch "main"=4 chars, all extra to dir
  # Path fits in 76 -> not truncated
  assert "$PROMPT" "%F{135}${wide_dir}%f %F{39}main%f %(#.#.%%)%f " "precmd: wide terminal, extra to dir"
fi

# 8. Tight terminal (COLUMNS=69, long branch) — branch truncated
#    COLUMNS=69 <= 80, extra=0, MIN_BRANCH=40, branch_cap=40
local tight_repo="$TMPDIR/tight_repo"
setup_git_repo "$tight_repo"
pushd -q "$tight_repo"
local long_branch="very-long-feature-branch-name-for-testing-purposes"
git checkout -b "$long_branch" 2>/dev/null
reset_globals
COLUMNS=69
:
_prompt_precmd
local expected_branch="very-long-feature-branch-name-fo...poses"
assert "$PROMPT" "%F{135}${tight_repo}%f %F{39}${expected_branch}%f %(#.#.%%)%f " "precmd: tight terminal, branch truncated"
popd -q

# 9. Detached HEAD in prompt -> @sha7
local detached_repo="$TMPDIR/detached_repo"
setup_git_repo "$detached_repo"
pushd -q "$detached_repo"
local sha_detached=$(git rev-parse HEAD)
git checkout "$sha_detached" 2>/dev/null
reset_globals
unset COLUMNS
:
_prompt_precmd
# Compute expected dir accounting for truncation (cap=36 when COLUMNS unset)
_prompt_truncate_dir "$detached_repo" 36
local sanitized_dir="${_prompt_dir_out//\%/%%}"
local expected_detached_branch="@${sha_detached:0:7}"
assert "$PROMPT" "%F{135}${sanitized_dir}%f %F{39}${expected_detached_branch}%f %(#.#.%%)%f " "precmd: detached HEAD"
popd -q

# 10. Root dir /
pushd -q /
reset_globals
unset COLUMNS
:
_prompt_precmd
assert "$PROMPT" "%F{135}/%f %(#.#.%%)%f " "precmd: root dir /"
popd -q

# ===================================================================
# Group 6: Performance (2 tests)
# ===================================================================
echo "=== Performance ==="
local perf_iterations=1000

# Performance test 1: no-git
pushd -q "$nogit_dir"
reset_globals
typeset -F perf_start=$SECONDS
repeat $perf_iterations; do _prompt_precmd; done
typeset -F perf_elapsed=$(( SECONDS - perf_start ))
((tests++))
if (( perf_elapsed < 1.0 )); then
  echo "PASS: performance (no-git) took ${perf_elapsed}s"
  ((passed++))
else
  echo "FAIL: performance (no-git) took ${perf_elapsed}s (expected <1s)"
  ((failed++))
fi
popd -q

# Performance test 2: git with branch
pushd -q "$prompt_git"
reset_globals
typeset -F perf2_start=$SECONDS
repeat $perf_iterations; do _prompt_precmd; done
typeset -F perf2_elapsed=$(( SECONDS - perf2_start ))
((tests++))
if (( perf2_elapsed < 1.0 )); then
  echo "PASS: performance (git+branch) took ${perf2_elapsed}s"
  ((passed++))
else
  echo "FAIL: performance (git+branch) took ${perf2_elapsed}s (expected <1s)"
  ((failed++))
fi
popd -q

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
