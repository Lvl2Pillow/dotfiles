#!/usr/bin/env zsh
# Unit tests for prompt rendering helpers.
# Tests pure functions: dir truncation, branch truncation, branch color mapping.
# No zle, no async, no signal handling, no widget wrappers.

_PROMPT_FORCE_LOAD=1
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

setup_git_repo() {
    local dir="$1"
    git init -b main "$dir" >/dev/null 2>&1
    (
        cd "$dir"
        git config user.email test@test
        git config user.name test
        echo init > init
        git add init
        git commit -m init >/dev/null 2>&1
    )
}

# Run _prompt_precmd with controlled state.
# _prompt_rerendering=1 suppresses async spawn.
# COLUMNS must be explicit; default 80 avoids COLUMNS=0 bug in CI shells.
run_precmd() {
    local exit_code="$1" dir="$2" staged="$3" unstaged="$4" untracked="${5:-0}" stash="${6:-0}"
    pushd -q "$dir"
    _prompt_git_staged=$staged
    _prompt_git_unstaged=$unstaged
    _prompt_git_untracked=$untracked
    _prompt_git_stashed=$stash
    _prompt_rerendering=1
    _prompt_last_exit=$exit_code
    COLUMNS=80
    _prompt_precmd
    _prompt_rerendering=0
    popd -q
}

local TMPDIR
TMPDIR=$(mktemp -d /tmp/test_prompt_XXXXXX)
trap "rm -rf $TMPDIR" EXIT INT TERM

# ===================================================================
# _prompt_truncate_dir
# ===================================================================
echo "=== _prompt_truncate_dir ==="

# below min cap: last N chars
_prompt_truncate_dir "abcdefghijklm" 8
assert "$_prompt_dir_out" "fghijklm" "below min cap: last 8"

# shorter than cap
_prompt_truncate_dir "foo" 10
assert "$_prompt_dir_out" "foo" "short dir unchanged"

# exactly at cap
_prompt_truncate_dir "1234567890" 10
assert "$_prompt_dir_out" "1234567890" "dir at cap unchanged"

# over cap: first 2 + ... + last (cap-5)
_prompt_truncate_dir "12345678901" 10
assert "$_prompt_dir_out" "12...78901" "dir over cap truncated"

# root
_prompt_truncate_dir "/" 10
assert "$_prompt_dir_out" "/" "root dir unchanged"

# empty
_prompt_truncate_dir "" 10
assert "$_prompt_dir_out" "" "empty dir unchanged"

# single char
_prompt_truncate_dir "a" 10
assert "$_prompt_dir_out" "a" "single-char dir unchanged"

# % passes through (escaping happens in precmd)
_prompt_truncate_dir "/tmp/50%off" 20
assert "$_prompt_dir_out" "/tmp/50%off" "dir with % untouched"

# ===================================================================
# _prompt_truncate_branch
# ===================================================================
echo "=== _prompt_truncate_branch ==="

# below min cap: first N chars
_prompt_truncate_branch "abcdefghijklmnopq" 10
assert "$_prompt_branch_out" "abcdefghij" "below min cap: first 10"

# shorter than cap
_prompt_truncate_branch "main" 40
assert "$_prompt_branch_out" "main" "short branch unchanged"

# exactly at cap
local b40="1234567890123456789012345678901234567890"
_prompt_truncate_branch "$b40" 40
assert "$_prompt_branch_out" "$b40" "branch at cap unchanged"

# over cap: first (cap-5) + ... + last 2
_prompt_truncate_branch "very-long-feature-branch-name-for-testing" 40
assert "$_prompt_branch_out" "very-long-feature-branch-name-for-t...ng" "branch over cap truncated"

# empty
_prompt_truncate_branch "" 40
assert "$_prompt_branch_out" "" "empty branch unchanged"

# single char
_prompt_truncate_branch "a" 40
assert "$_prompt_branch_out" "a" "single-char branch unchanged"

# slashes not split, truncated as one string
_prompt_truncate_branch "feature/some/branch" 40
assert "$_prompt_branch_out" "feature/some/branch" "branch with slashes unchanged"

# ===================================================================
# Branch color mapping via _prompt_precmd
# ===================================================================
echo "=== Branch color ==="

local clean="$TMPDIR/clean"
setup_git_repo "$clean"

# clean: green (fg=34)
run_precmd 0 "$clean" 0 0 0 0
assert "${_prompt_rh_colors[*]}" "fg=135 fg=34" "clean: green"

# staged only: yellow (fg=220)
run_precmd 0 "$clean" 1 0 0 0
assert "${_prompt_rh_colors[*]}" "fg=135 fg=220" "staged: yellow"

# unstaged only: orange (fg=208)
run_precmd 0 "$clean" 0 1 0 0
assert "${_prompt_rh_colors[*]}" "fg=135 fg=208" "unstaged: orange"

# staged + unstaged: orange wins (unstaged higher priority)
run_precmd 0 "$clean" 1 1 0 0
assert "${_prompt_rh_colors[*]}" "fg=135 fg=208" "staged+unstaged: orange wins"

# untracked only: dark red (fg=88)
run_precmd 0 "$clean" 0 0 1 0
assert "${_prompt_rh_colors[*]}" "fg=135 fg=88" "untracked: dark red"

# stash only: lime (fg=112)
run_precmd 0 "$clean" 0 0 0 1
assert "${_prompt_rh_colors[*]}" "fg=135 fg=112" "stash: lime"

# all flags: untracked wins (highest priority)
run_precmd 0 "$clean" 1 1 1 1
assert "${_prompt_rh_colors[*]}" "fg=135 fg=88" "all flags: untracked wins"

# Stale globals persist across cd until async completes — intended behavior.
# When entering a clean repo with stale _prompt_git_untracked=1 from previous dir,
# the footer briefly shows dark red (88) until async callback overwrites with green.
pushd -q "$clean"
_prompt_git_untracked=1
_prompt_rerendering=0
COLUMNS=80
_prompt_precmd
popd -q
assert "${_prompt_rh_colors[*]}" "fg=135 fg=88" "stale globals: dark red shown until async completes"
_prompt_git_untracked=0

# ===================================================================
# _prompt_git_branch — detached HEAD
# ===================================================================
echo "=== Detached HEAD ==="

local detached="$TMPDIR/detached"
setup_git_repo "$detached"
pushd -q "$detached"
git checkout --detach HEAD >/dev/null 2>&1
_prompt_git_branch
assert "$_prompt_branch_out" "@${$(git rev-parse --short HEAD):0:7}" "detached HEAD: @<hash>"
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
