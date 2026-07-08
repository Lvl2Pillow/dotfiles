#!/usr/bin/env zsh
# Unit tests for 0X_prompt.zsh — prompt rendering logic.
# Covers pure helpers (truncation, git detection, signal handler) and
# _prompt_precmd PROMPT assembly. The async worker (ZLE/SIGUSR1 wiring)
# requires an interactive shell and is not exercised here.

source "${0:A:h}/../../dot_zsh/05_prompt.zsh" 2>/dev/null

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

assert_rc() {
  local actual="$1" expected="$2" name="$3"
  ((tests++))
  if [[ "$actual" -eq "$expected" ]]; then
    ((passed++))
  else
    echo "FAIL: $name"
    echo "  expected rc: $expected"
    echo "  got rc:      $actual"
    ((failed++))
  fi
}

# Create a minimal git repo with one commit on main.
setup_git_repo() {
  local dir="$1"
  git init -b main "$dir" >/dev/null 2>&1
  ( cd "$dir"
    git config user.email test@test
    git config user.name test
    echo init > init
    git add init
    git commit -m init >/dev/null 2>&1 )
}

# Run _prompt_precmd inside $dir with simulated async state.
# _prompt_rendering=1 suppresses the background async spawn so tests stay
# deterministic; staged/unstaged are set directly to drive branch coloring.
run_precmd() {
  local exit_code="$1" cols="$2" dir="$3" staged="$4" unstaged="$5" untracked="${6:-0}" stash="${7:-0}"
  pushd -q "$dir"
  _prompt_git_staged=$staged
  _prompt_git_unstaged=$unstaged
  _prompt_git_untracked=$untracked
  _prompt_git_stashed=$stash
  _prompt_rendering=1
  _prompt_last_exit=$exit_code
  if [[ -n "$cols" ]]; then COLUMNS=$cols; else unset COLUMNS; fi
  _prompt_precmd
  _prompt_rendering=0
  popd -q
}

local TMPDIR
TMPDIR=$(mktemp -d /tmp/test_prompt_XXXXXX)
trap "rm -rf $TMPDIR" EXIT INT TERM

# ===================================================================
# _prompt_truncate_dir — pure string truncation
# ===================================================================
echo "=== _prompt_truncate_dir ==="

# shorter than cap → unchanged
_prompt_truncate_dir "foo" 10
assert "$_prompt_dir_out" "foo" "short dir unchanged"

# exactly at cap → unchanged
_prompt_truncate_dir "1234567890" 10
assert "$_prompt_dir_out" "1234567890" "dir at cap unchanged"

# over cap → first 2 chars + ... + trailing (cap-5) chars
_prompt_truncate_dir "12345678901" 10
assert "$_prompt_dir_out" "12...78901" "dir over cap truncated"

# minimum cap (6) → only the head/tail bookends fit
_prompt_truncate_dir "abcdefg" 6
assert "$_prompt_dir_out" "ab...g" "dir at min cap 6"

# root path → unchanged
_prompt_truncate_dir "/" 10
assert "$_prompt_dir_out" "/" "root dir unchanged"

# empty string → unchanged
_prompt_truncate_dir "" 10
assert "$_prompt_dir_out" "" "empty dir unchanged"

# single char → unchanged
_prompt_truncate_dir "a" 10
assert "$_prompt_dir_out" "a" "single-char dir unchanged"

# literal % must pass through untouched (escaping is precmd's job)
_prompt_truncate_dir "/tmp/50%off" 20
assert "$_prompt_dir_out" "/tmp/50%off" "dir with % untouched"

# ===================================================================
# _prompt_truncate_branch — pure string truncation
# ===================================================================
echo "=== _prompt_truncate_branch ==="

# shorter than cap → unchanged
_prompt_truncate_branch "main" 40
assert "$_prompt_branch_out" "main" "short branch unchanged"

# exactly at cap → unchanged
local b40="1234567890123456789012345678901234567890"
_prompt_truncate_branch "$b40" 40
assert "$_prompt_branch_out" "$b40" "branch at cap unchanged"

# over cap → first (cap-8) chars + ... + trailing 5 chars
_prompt_truncate_branch "very-long-feature-branch-name-for-testing-purposes" 40
assert "$_prompt_branch_out" "very-long-feature-branch-name-fo...poses" "branch over cap truncated"

# minimum cap (8) → only the tail bookend fits
_prompt_truncate_branch "123456789" 8
assert "$_prompt_branch_out" "...56789" "branch at min cap 8"

# empty string → unchanged
_prompt_truncate_branch "" 40
assert "$_prompt_branch_out" "" "empty branch unchanged"

# single char → unchanged
_prompt_truncate_branch "a" 40
assert "$_prompt_branch_out" "a" "single-char branch unchanged"

# branch names containing slashes are not split — truncated as one string
_prompt_truncate_branch "feature/some/branch" 40
assert "$_prompt_branch_out" "feature/some/branch" "branch with slashes unchanged"

# ===================================================================
# _prompt_find_git — repo detection + cache + worktree
# ===================================================================
echo "=== _prompt_find_git ==="

local saved_dir_cache=$_prompt_dir_cache
local saved_is_cache=$_prompt_is_git_cache
local saved_git_dir_cache=$_prompt_git_dir_cache

# plain directory with no .git → returns 1 and caches the miss
mkdir -p "$TMPDIR/plain"
_prompt_dir_cache=""; _prompt_is_git_cache=0; _prompt_git_dir_cache=""
pushd -q "$TMPDIR/plain"
_prompt_find_git; local rc=$?
assert_rc $rc 1 "plain dir returns 1"
assert "$_prompt_dir_cache" "$TMPDIR/plain" "plain dir caches PWD"
assert "$_prompt_git_dir_cache" "" "plain dir leaves git_dir empty"
popd -q

# real git repo → returns 0 and caches the .git path
local clean="$TMPDIR/clean"
setup_git_repo "$clean"
_prompt_dir_cache=""; _prompt_is_git_cache=0; _prompt_git_dir_cache=""
pushd -q "$clean"
_prompt_find_git; rc=$?
assert_rc $rc 0 "git repo returns 0"
assert "$_prompt_git_dir_cache" "$clean/.git" "git repo caches .git path"
popd -q

# cache hit on same git repo → returns 0 without re-walking
_prompt_dir_cache="$clean"; _prompt_is_git_cache=1; _prompt_git_dir_cache="$clean/.git"
pushd -q "$clean"
_prompt_find_git; rc=$?
assert_rc $rc 0 "git repo cache hit returns 0"
popd -q

# cache hit on same non-git dir → returns 1 without re-walking
_prompt_dir_cache="$TMPDIR/plain"; _prompt_is_git_cache=0
pushd -q "$TMPDIR/plain"
_prompt_find_git; rc=$?
assert_rc $rc 1 "non-git cache hit returns 1"
popd -q

# different PWD invalidates the cache → fresh walk
local other_plain="$TMPDIR/other_plain"
mkdir -p "$other_plain"
_prompt_dir_cache="$TMPDIR/plain"; _prompt_is_git_cache=0
pushd -q "$other_plain"
_prompt_find_git; rc=$?
assert_rc $rc 1 "new dir triggers re-walk"
assert "$_prompt_dir_cache" "$other_plain" "new dir updates cache"
popd -q

# git worktree: .git is a file pointing elsewhere → resolved and cached
local worktree="$TMPDIR/worktree"
setup_git_repo "$worktree"
mv "$worktree/.git" "$worktree/actual_git"
echo "gitdir: $worktree/actual_git" > "$worktree/.git"
local worktree_resolved="$worktree/actual_git"
worktree_resolved="${worktree_resolved:A}"
_prompt_dir_cache=""; _prompt_is_git_cache=0; _prompt_git_dir_cache=""
pushd -q "$worktree"
_prompt_find_git; rc=$?
assert_rc $rc 0 "worktree returns 0"
assert "$_prompt_git_dir_cache" "$worktree_resolved" "worktree resolves gitdir"
popd -q

# .git directory without HEAD file → not treated as a repo
local nohead="$TMPDIR/nohead"
mkdir -p "$nohead/.git"
echo "[core]" > "$nohead/.git/config"
_prompt_dir_cache=""; _prompt_is_git_cache=0; _prompt_git_dir_cache=""
pushd -q "$nohead"
_prompt_find_git; rc=$?
assert_rc $rc 1 "incomplete .git (no HEAD) returns 1"
assert "$_prompt_git_dir_cache" "" "incomplete .git leaves git_dir empty"
popd -q

# cached git dir loses HEAD → cache invalidated, fresh walk returns 1
local bak_head
bak_head=$(< "$clean/.git/HEAD")
rm "$clean/.git/HEAD"
_prompt_dir_cache="$clean"; _prompt_is_git_cache=1; _prompt_git_dir_cache="$clean/.git"
pushd -q "$clean"
_prompt_find_git; rc=$?
assert_rc $rc 1 "cached repo with missing HEAD returns 1"
assert "$_prompt_is_git_cache" "0" "missing HEAD invalidates cache flag"
popd -q
echo "$bak_head" > "$clean/.git/HEAD"

# worktree with relative gitdir path → :A resolves to absolute
local rel_worktree="$TMPDIR/rel_worktree"
setup_git_repo "$rel_worktree"
mv "$rel_worktree/.git" "$rel_worktree/actual_git"
echo "gitdir: actual_git" > "$rel_worktree/.git"
_prompt_dir_cache=""; _prompt_is_git_cache=0; _prompt_git_dir_cache=""
pushd -q "$rel_worktree"
_prompt_find_git; rc=$?
assert_rc $rc 0 "worktree with relative gitdir returns 0"
local rel_resolved="$rel_worktree/actual_git"
rel_resolved="${rel_resolved:A}"
assert "$_prompt_git_dir_cache" "$rel_resolved" "worktree resolves relative gitdir"
popd -q
_prompt_dir_cache=$saved_dir_cache
_prompt_is_git_cache=$saved_is_cache
_prompt_git_dir_cache=$saved_git_dir_cache

# ===================================================================
# _prompt_signal_handler — consumes async result files
# ===================================================================
echo "=== _prompt_signal_handler ==="

local save_staged=$_prompt_git_staged
local save_unstaged=$_prompt_git_unstaged
local save_untracked=$_prompt_git_untracked
local save_stash=$_prompt_git_stashed
local save_counter=$_prompt_async_counter
rm -f $_prompt_async_out

# no result file → state untouched
_prompt_git_staged=99; _prompt_git_unstaged=99; _prompt_git_untracked=99; _prompt_git_stashed=99
_prompt_signal_handler
assert "$_prompt_git_staged" "99" "no file: staged unchanged"
assert "$_prompt_git_unstaged" "99" "no file: unstaged unchanged"
assert "$_prompt_git_untracked" "99" "no file: untracked unchanged"
assert "$_prompt_git_stashed" "99" "no file: stash unchanged"

# matching counter → state updated and file consumed
_prompt_async_counter=5
echo "0|1|0|0|5" > "$_prompt_async_out"
_prompt_git_staged=99; _prompt_git_unstaged=99; _prompt_git_untracked=99; _prompt_git_stashed=99
_prompt_signal_handler
assert "$_prompt_git_staged" "0" "matching counter: staged=0"
assert "$_prompt_git_unstaged" "1" "matching counter: unstaged=1"
assert "$_prompt_git_untracked" "0" "matching counter: untracked=0"
assert "$_prompt_git_stashed" "0" "matching counter: stash=0"
[[ ! -f $_prompt_async_out ]]; assert "$?" "0" "matching counter: file deleted"

# matching counter with untracked=1 and stash=1
_prompt_async_counter=5
echo "0|0|1|1|5" > "$_prompt_async_out"
_prompt_git_staged=99; _prompt_git_unstaged=99; _prompt_git_untracked=99; _prompt_git_stashed=99
_prompt_signal_handler
assert "$_prompt_git_staged" "0" "untracked+stash: staged=0"
assert "$_prompt_git_unstaged" "0" "untracked+stash: unstaged=0"
assert "$_prompt_git_untracked" "1" "untracked+stash: untracked=1"
assert "$_prompt_git_stashed" "1" "untracked+stash: stash=1"
[[ ! -f $_prompt_async_out ]]; assert "$?" "0" "untracked+stash: file deleted"

# stale counter (mismatched) → state untouched, file still deleted
_prompt_async_counter=10
echo "1|1|1|1|5" > "$_prompt_async_out"
_prompt_git_staged=99; _prompt_git_unstaged=99; _prompt_git_untracked=99; _prompt_git_stashed=99
_prompt_signal_handler
assert "$_prompt_git_staged" "99" "stale counter: staged unchanged"
assert "$_prompt_git_unstaged" "99" "stale counter: unstaged unchanged"
assert "$_prompt_git_untracked" "99" "stale counter: untracked unchanged"
assert "$_prompt_git_stashed" "99" "stale counter: stash unchanged"
[[ ! -f $_prompt_async_out ]]; assert "$?" "0" "stale counter: file deleted"

# malformed payload (no pipes) → state untouched, file deleted
_prompt_async_counter=7
echo "garbage" > "$_prompt_async_out"
_prompt_git_staged=99; _prompt_git_unstaged=99; _prompt_git_untracked=99; _prompt_git_stashed=99
_prompt_signal_handler
assert "$_prompt_git_staged" "99" "malformed: staged unchanged"
assert "$_prompt_git_unstaged" "99" "malformed: unstaged unchanged"
assert "$_prompt_git_untracked" "99" "malformed: untracked unchanged"
assert "$_prompt_git_stashed" "99" "malformed: stash unchanged"
[[ ! -f $_prompt_async_out ]]; assert "$?" "0" "malformed: file deleted"

_prompt_async_counter=$save_counter
_prompt_git_staged=$save_staged
_prompt_git_unstaged=$save_unstaged
_prompt_git_untracked=$save_untracked
_prompt_git_stashed=$save_stash
rm -f $_prompt_async_out

# ===================================================================
# _prompt_precmd — PROMPT assembly
# ===================================================================
echo "=== _prompt_precmd ==="

local nogit="$TMPDIR/nogit"
mkdir -p "$nogit"

# no repo, success → symbol uses default foreground (no color escape)
run_precmd 0 "" "$nogit" 0 0
assert "$PROMPT" "%F{135}${nogit}%f %(#.#.%%)%f " "no repo, exit 0: default symbol"

# no repo, failure → symbol turns red
run_precmd 1 "" "$nogit" 0 0
assert "$PROMPT" "%F{135}${nogit}%f %F{196}%(#.#.%%)%f " "no repo, exit 1: red symbol"

# clean repo → green branch
run_precmd 0 "" "$clean" 0 0
assert "$PROMPT" "%F{135}${clean}%f %F{35}main%f %(#.#.%%)%f " "clean repo: green branch"

# staged only → yellow branch
run_precmd 0 "" "$clean" 1 0
assert "$PROMPT" "%F{135}${clean}%f %F{220}main%f %(#.#.%%)%f " "staged only: yellow branch"

# unstaged only → orange branch
run_precmd 0 "" "$clean" 0 1
assert "$PROMPT" "%F{135}${clean}%f %F{208}main%f %(#.#.%%)%f " "unstaged only: orange branch"

# both staged and unstaged → unstaged wins (orange)
run_precmd 0 "" "$clean" 1 1
assert "$PROMPT" "%F{135}${clean}%f %F{208}main%f %(#.#.%%)%f " "staged+unstaged: orange wins"

# detached HEAD → branch shown as @<short sha>, colored clean (green)
local detached="$TMPDIR/detached"
setup_git_repo "$detached"
pushd -q "$detached"
local sha=$(git rev-parse HEAD)
git checkout "$sha" 2>/dev/null
popd -q
run_precmd 0 "" "$detached" 0 0
assert "$PROMPT" "%F{135}${detached}%f %F{35}@${sha:0:7}%f %(#.#.%%)%f " "detached HEAD: @<sha>"

# $PWD under $HOME → rendered as ~/...
local home_dir="$TMPDIR/home_test"
mkdir -p "$home_dir/subdir"
local saved_home="$HOME"
HOME="$home_dir"
run_precmd 0 "" "$home_dir/subdir" 0 0
assert "$PROMPT" "%F{135}~/subdir%f %(#.#.%%)%f " "HOME substitution: ~"
HOME="$saved_home"

# literal % in dir name → doubled to %% so it renders literally
local percent_dir="$TMPDIR/d%p"
mkdir -p "$percent_dir"
run_precmd 0 "" "$percent_dir" 0 0
assert "$PROMPT" "%F{135}${TMPDIR}/d%%p%f %(#.#.%%)%f " "percent in dir: escaped to %%"

# root dir / → rendered as a single slash
run_precmd 0 "" "/" 0 0
assert "$PROMPT" "%F{135}/%f %(#.#.%%)%f " "root dir /"

# tight terminal (COLUMNS<80) → long branch truncated at cap 40
local tight="$TMPDIR/tight"
setup_git_repo "$tight"
local long_branch="very-long-feature-branch-name-for-testing-purposes"
pushd -q "$tight"; git checkout -b "$long_branch" 2>/dev/null; popd -q
run_precmd 0 "69" "$tight" 0 0
assert "$PROMPT" "%F{135}${tight}%f %F{35}very-long-feature-branch-name-fo...poses%f %(#.#.%%)%f " "tight terminal: branch truncated"

# wide terminal (COLUMNS=120) with short dir+branch → no truncation, extra unused
run_precmd 0 "120" "$clean" 0 0
assert "$PROMPT" "%F{135}${clean}%f %F{35}main%f %(#.#.%%)%f " "wide terminal: no truncation"

# untracked only → red branch (highest priority)
run_precmd 0 "" "$clean" 0 0 1 0
assert "$PROMPT" "%F{135}${clean}%f %F{196}main%f %(#.#.%%)%f " "untracked only: red branch"

# stash only (clean repo) → lime branch
run_precmd 0 "" "$clean" 0 0 0 1
assert "$PROMPT" "%F{135}${clean}%f %F{112}main%f %(#.#.%%)%f " "stash only: lime branch"



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
