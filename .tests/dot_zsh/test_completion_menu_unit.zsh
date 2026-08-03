#!/usr/bin/env zsh
# Unit tests for the completion-menu footer-hiding logic in 05_prompt.zsh.
#
# Covers:
#   - _prompt_is_completion_widget classification (pure, no zle needed)
#   - _prompt_menu_active init
#   - completion widgets wrapped with _prompt_completion_wrap + backup aliases
#   - wrap idempotence when the file is sourced again
#
# Needs zsh/zle + compinit so the completion widgets exist.
#
# Run: zsh .tests/dot_zsh/test_completion_menu_unit.zsh

zmodload zsh/zle zsh/zleparameter 2>/dev/null
autoload -Uz compinit
compinit -u -i

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

# ---- _prompt_is_completion_widget classification ----
# Widgets that can display the completion list -> rc 0
local rc
for w in \
    expand-or-complete expand-or-complete-prefix complete-word \
    menu-complete reverse-menu-complete menu-expand-or-complete \
    accept-and-menu-complete complete-or-list list-choices list-expand \
    delete-char-or-list _complete_help complete-in-word \
    history-complete-newer history-complete-older \
    _prompt_orig_expand-or-complete; do
    _prompt_is_completion_widget "$w"; rc=$?
    assert_rc $rc 0 "is_completion_widget: $w"
done

# Widgets that do NOT keep the completion list -> rc 1
for w in \
    accept-line self-insert backward-char forward-char backward-delete-char \
    kill-line undo _prompt_esc_enter_newline zle-line-pre-redraw ''; do
    _prompt_is_completion_widget "$w"; rc=$?
    assert_rc $rc 1 "not_completion_widget: '${w:-<empty>}'"
done

# ---- state init ----
assert "$_prompt_menu_active" "0" "menu_active init 0"

# ---- stale-row clearing helper ----
assert "${+functions[_prompt_zle_clear_list_area]}" "1" \
    "clear_list_area helper defined"
# zle -R -c must parse as a valid zle command (it is silently rejected with
# status 1 when zle is not active, as here).
_prompt_zle_clear_list_area; rc=$?
assert_rc $rc 1 "zle -R -c valid (status 1 outside zle)"

# ---- pre-redraw delegates to append_footer (footer logic is unified) ----
assert "${+functions[_prompt_zle_pre_redraw]}" "1" "pre_redraw defined"
assert "${+functions[_prompt_zle_append_footer]}" "1" "append_footer defined"

# ---- widget wrapping ----
# Backup aliases exist for the widgets that were present at source time.
assert_rc "$(zle -la _prompt_orig_expand-or-complete >/dev/null 2>&1; echo $?)" 0 \
    "backup alias exists: expand-or-complete"
assert_rc "$(zle -la _prompt_orig_complete-word >/dev/null 2>&1; echo $?)" 0 \
    "backup alias exists: complete-word"
assert_rc "$(zle -la _prompt_orig_menu-complete >/dev/null 2>&1; echo $?)" 0 \
    "backup alias exists: menu-complete"
assert_rc "$(zle -la _prompt_orig_list-choices >/dev/null 2>&1; echo $?)" 0 \
    "backup alias exists: list-choices"

# The widgets are redefined to _prompt_completion_wrap.
assert "${widgets[expand-or-complete]}" "user:_prompt_completion_wrap" \
    "expand-or-complete wrapped"
assert "${widgets[complete-word]}" "user:_prompt_completion_wrap" \
    "complete-word wrapped"
assert "${widgets[menu-complete]}" "user:_prompt_completion_wrap" \
    "menu-complete wrapped"
assert "${widgets[list-choices]}" "user:_prompt_completion_wrap" \
    "list-choices wrapped"

# Non-completion widgets must be untouched (accept-line is wrapped only by
# the prompt file's own accept handler, never by the completion wrapper).
assert "${widgets[self-insert]}" "builtin" "self-insert not wrapped"
assert "${widgets[accept-line]}" "user:_prompt_zle_accept_line" \
    "accept-line not completion-wrapped"

# ---- idempotence: re-source must not double-wrap ----
source "${0:A:h}/../../dot_zsh/05_prompt.zsh" 2>/dev/null
assert "${widgets[expand-or-complete]}" "user:_prompt_completion_wrap" \
    "expand-or-complete still wrapped once after re-source"
assert_rc "$(zle -la _prompt_orig_expand-or-complete >/dev/null 2>&1; echo $?)" 0 \
    "backup alias intact after re-source"
assert "$_prompt_menu_active" "0" "menu_active reset by re-source"

# ---- summary ----
echo
echo "$passed/$tests passed"
(( failed == 0 ))
