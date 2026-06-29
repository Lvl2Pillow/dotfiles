#!/usr/bin/env zsh
# Unit tests for 5_prompt.zsh
# Run: zsh test_prompt.zsh

source "${0:h}/../5_prompt.zsh"

local tests=0
local passed=0
local failed=0

assert() {
  local actual="$1"
  local expected="$2"
  local name="$3"
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

echo "=== _prompt_truncate_dir ==="

# short dir unchanged
_prompt_truncate_dir "/home/user" 20
assert "$_prompt_dir_out" "/home/user" "short dir: unchanged"

# dir exactly at cap
_prompt_truncate_dir "/home/user/project" 18
assert "$_prompt_dir_out" "/home/user/project" "dir at cap: unchanged"

# long dir truncated — first 2 + ... + last (cap-5)
# "/home/user/very/long/path/to/some/project" is 41 chars → ending at cap-5=15 → "to/some/project"
_prompt_truncate_dir "/home/user/very/long/path/to/some/project" 20
assert "$_prompt_dir_out" "/h...to/some/project" "long dir: truncated to 20"

# very short cap
# "/a/very/long/directory/path/name" is 31 chars → ending at cap-5=5 → "/name"
_prompt_truncate_dir "/a/very/long/directory/path/name" 10
assert "$_prompt_dir_out" "/a.../name" "long dir: truncated to 10"

# root-relative
_prompt_truncate_dir "/" 36
assert "$_prompt_dir_out" "/" "root dir: unchanged"

echo
echo "=== _prompt_truncate_branch ==="

# short branch unchanged
_prompt_truncate_branch "main" 40
assert "$_prompt_branch_out" "main" "short branch: unchanged"

# branch exactly at cap
_prompt_truncate_branch "feature/main-ck" 16
assert "$_prompt_branch_out" "feature/main-ck" "branch at cap: unchanged"

# long branch truncated — first (cap-8) + ... + last 5
# "feature/very-long-branch-name-that-is-long" is 42 chars → beginning at 40-8=32 → "feature/very-long-branch-name-th"
_prompt_truncate_branch "feature/very-long-branch-name-that-is-long" 40
assert "$_prompt_branch_out" "feature/very-long-branch-name-th...-long" "long branch: truncated to 40"

# very short cap
_prompt_truncate_branch "abcdefghijklmnopqrstuvwxyz" 10
assert "$_prompt_branch_out" "ab...vwxyz" "long branch: truncated to 10"

# min possible cap (8 or less — ending alone fits nothing)
_prompt_truncate_branch "toolongbranch" 8
assert "$_prompt_branch_out" "...ranch" "branch: truncated to 8"

echo
echo "=== _prompt_precmd ==="

# Test PROMPT structure in a clean environment
local old_pwd="$PWD"
local old_columns="$COLUMNS"
COLUMNS=80
PWD="/tmp/test_prompt"

# no git dir — PROMPT should be: <blue dir>%f %f <symbol>%f
true
_prompt_precmd
assert "$PROMPT" "%F{39}/tmp/test_prompt%f %(#.#.%%)%f " "precmd: no git, success (default white)"

# with exit failure — symbol should be preceded by %F{196} (bright red)
false
_prompt_precmd
assert "$PROMPT" "%F{39}/tmp/test_prompt%f %F{196}%(#.#.%%)%f " "precmd: no git, failure (bright red)"

# restore
PWD="$old_pwd"
COLUMNS="$old_columns"

echo
echo "=== Results: $passed/$tests passed ==="

if (( failed )); then
  echo "FAILURES: $failed"
  exit 1
fi
exit 0
