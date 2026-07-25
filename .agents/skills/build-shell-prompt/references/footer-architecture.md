# Footer Architecture

## POSTDISPLAY Layout

```
POSTDISPLAY = [ghost text]\n[directory] |[branch]  [truncation_marker]
             ↑______ first line _____↑↑__ second line (footer) __↑
```

Ghost text is autosuggest's predicted completion (empty if no suggestion).
Footer is directory | branch with trailing space.

## region_highlight Management

Colors via `region_highlight`, NOT escape codes in PROMPT. `_prompt_rh_colors` array set by `_prompt_precmd` unconditionally.

Branch colors: `34`=green(clean), `88`=darkred(untracked), `208`=orange(unstaged), `220`=yellow(staged), `112`=lime(stashed).

### Helper: _prompt_update_region_highlight

```zsh
_prompt_update_region_highlight() {
    # Remove old footer entries by matching stored positions
    region_highlight=(
        "${(@)region_highlight:#${_prompt_rh_positions[1]} *}"
        "${(@)region_highlight:#${_prompt_rh_positions[2]} *}"
    )

    # Compute positions from current BUFFER/POSTDISPLAY
    local prompt_start=$((${#BUFFER} + ${#POSTDISPLAY} - ${#_prompt}))
    local -a parts=("${(@s:|:)${_prompt}}")
    local dir_len=${#parts[1]}
    local dir_end=$((prompt_start + dir_len))
    local branch_end=$((prompt_start + ${#_prompt} - 1))  # -1 for trailing space

    local pos1="${prompt_start} ${dir_end}"
    local pos2="${dir_end} ${branch_end}"

    _prompt_rh_positions=("$pos1" "$pos2")
    region_highlight+=(
        "$pos1 ${_prompt_rh_colors[1]}"
        "$pos2 ${_prompt_rh_colors[2]}"
    )
}
```

### Cleanup pattern

`"${(@)region_highlight:#${pos} *}"` removes entries matching start/end positions. Safe because:
- Won't match autosuggest's ghost highlight (different positions)
- Pattern includes trailing space + `*` — won't match other positions with same start but different end

### Calling contexts

Called from:
1. `_prompt_zle_append_footer` (autosuggest wrapper path — also sets POSTDISPLAY)
2. `_prompt_zle_pre_redraw` (safety net hook)
3. `_prompt_async_callback` (only colors changed, text unchanged — no POSTDISPLAY update needed)

Must NEVER be called from signal context — no `2>/dev/null` guards.

## _prompt_zle_append_footer

```zsh
_prompt_zle_append_footer() {
    emulate -L zsh
    if [[ $WIDGET = *accept-* ]]; then
        return 0
    fi

    # strip old footer, keep only ghost text (before first \n)
    local ghost="${POSTDISPLAY%%$'\n'*}"
    POSTDISPLAY="${ghost}"$'\n'"${_prompt}"

    _prompt_update_region_highlight
}
```

## Truncation

Footer text is truncated to `COLUMNS - 5` to leave room for ghost text and right margin. Truncation uses zsh's `$COLUMNS` at precmd time — does NOT update during editing.

On terminal resize during editing:
- Shrinking: text wraps at new width (zle's natural line wrapping handles it)
- Growing: unused space visible until next Enter (precmd recomputes)
