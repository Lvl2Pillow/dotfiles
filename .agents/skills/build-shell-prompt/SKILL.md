---
name: build-shell-prompt
description: "Build zsh prompts. zle, PS1, POSTDISPLAY, region_highlight FIFO, autocomplete."
---

# Build Shell Prompt

Two-line zsh prompt. Symbol on line 1 (`% `). Directory and git info on line 2.

## Footer

Use `POSTDISPLAY`. Not `RPROMPT`.

```
POSTDISPLAY = <ghost_text>\n<prompt_text>
```

Autosuggest puts ghost text before the newline. Footer goes after it. Colors use `region_highlight`, not escape codes in PROMPT.

Branch colors: 34=green(clean), 88=darkred(untracked), 208=orange(unstaged), 220=yellow(staged), 112=lime(stashed).

`_prompt_precmd` sets `_prompt_rh_colors`. `_prompt_update_region_highlight` applies them to `region_highlight`. Only call from zle widget context. Signal context makes `region_highlight` read-only.

## Async Git Status

Do not use TRAPUSR1. Use a session-lifetime FIFO with `zle -F -w` callback.

```
Startup:  rm -f fifo, mkfifo, exec {fd}<>fifo
precmd:   increment counter, fork subshell
          subshell: git status -> pipe-delimited result -> FIFO
zle-line-init: zle -N callback, zle -F -w $fd callback
Callback: read FIFO, validate counter, update globals,
          _prompt_precmd, _prompt_update_region_highlight, zle .redisplay
```

### Two requirements

1.  **`zle -F -w`**. Without `-w`, zsh calls the handler as a plain shell function. `region_highlight`, `BUFFER`, `POSTDISPLAY` are not in scope. `zle .redisplay` does not work. With `-w`, full widget context is available.

2.  **`zle .redisplay`** is the only way to re-render `region_highlight`. `zle -R` does not re-apply it. Call `zle -R` before `.redisplay` to avoid the line-eating bug.

### Counter filtering

`_prompt_async_counter` increments every precmd. The async result includes the counter value. The callback discards data when the counter does not match. This prevents stale results from a slow async overwriting the current directory's state.

See `references/async-git.md`.

## Autosuggest Integration

Autosuggest uses `POSTDISPLAY` for ghost text. The footer shares the same variable.

Autosuggest categorizes widgets into 5 actions. Each wrapper saves, clears, or restores `POSTDISPLAY`. Your hook runs inside `_zsh_autosuggest_highlight_apply`, after autosuggest sets the ghost text.

| Action | Widgets | Footer handling |
|--------|---------|----------------|
| `clear` | accept-line, history-search*, up/down-line-or-* | POSTDISPLAY= before original |
| `accept` | forward-char, end-of-line | Strip footer, accept ghost into BUFFER |
| `execute` | (none default) | Strip footer, accept, submit |
| `partial_accept` | forward-word | Strip footer, move one word from ghost into BUFFER |
| `modify` | Everything else | Strip footer for `*accept-*` widgets only |

### Accept-and-hold stale footer

`accept-and-hold` goes through the `modify` wrapper, not `clear` like `accept-line`. The `modify` wrapper restores `POSTDISPLAY` after the widget returns. `zle -R` then redraws the stale footer. trashzle leaves it on row 1.

Strip the footer before the original saves `orig_postdisplay`.

```zsh
_zsh_autosuggest_modify() {
    [[ $WIDGET = *accept-* ]] && POSTDISPLAY="${POSTDISPLAY%%$'\n'*}"
    _prompt_autosuggest_modify_orig "$@"
}
```

Affects `accept-and-hold`, `accept-and-infer-next-history`, `accept-line-and-down-history`.

## Signal Handling

### Ctrl+C

Ctrl+C is the terminal's INTR character. The byte 0x03 never enters zle. `send-break` widget never dispatches.

```
Ctrl+C -> SIGINT -> TRAPINT -> errflag -> zle aborts -> trashzle()
  -> zrefresh() renders POSTDISPLAY (no guard for trashedzle)
  -> moveto(nlnct, 0) outputs one \n per display line
  -> Two lines: TWO \n -> blank line row
```

`zle-line-finish` does not fire on signal exit. The guard is `if (done && !errflag)` in `zleread()`. Detect aborted state with `[[ -n $ZLE_LINE_ABORTED ]]` in `zle-line-init`.

### send-break

`^G` or `^^` bound to `send-break`. It does not clear `POSTDISPLAY`. Footer persists after the buffer clears.

```zsh
zle -N send-break 'POSTDISPLAY=; zle .send-break'
```

## Testing

Use PTY (`pty.fork()`). Not probes that skip config loading. The test `.zshrc` must source the real prompt file.

```python
found = re.findall(rb'38;5;(\d+)', out)
```

See `references/testing.md`.

## Pitfalls

### Architecture
-   **TRAPUSR1 + printf is fragile**. Signal context blocks `region_highlight`. printf escape codes break on multiline buffers and new tabs. Use FIFO + `zle -F -w`.
-   **`zle -F` without `-w`** silences `region_highlight`, `BUFFER`, `POSTDISPLAY`. No error. Empty values. Always use `-w`.
-   **`zle -R` does not re-render `region_highlight`**. Only `zle .redisplay` runs the full display pipeline. Call `zle -R` before `.redisplay` to prevent the line-eating bug.
-   **`zle -F -w` handler must be a registered widget first**. `zle -N my_callback` before `zle -F -w $fd my_callback`. Otherwise zle ignores the registration.
-   **POSTDISPLAY survives trashzle**. zrefresh uses a buffer-level copy. Clearing POSTDISPLAY in TRAPINT is not enough. Use `\033[A` in PROMPT or detect aborted state.

### FIFO / async
-   **Open FIFO for read and write**: `exec {fd}<>"$fifo"`. Read-only causes `read` to block forever after consuming all data.
-   **Clean FIFO before creation**: `rm -f "$fifo"` before `mkfifo`. Stale FIFO from a previous session with the same PID causes silent failure.
-   **mkfifo can fail** on read-only filesystems. Fall back to disabling async.
-   **Async subshell needs counter and fifo path**. Forked subshell does not inherit zle context. Pass these as local variables before forking.
-   **Fork guard in precmd**. Do not start a new async while the previous one is still running. Use a guard variable.
-   **`$? > 1` is wrong for git status**. `git status --porcelain` returns 0 for clean and dirty, 1 for error. Only 128+ is fatal. Use `$? != 0` or `|| exit`.

### Autosuggest
-   **Modify wrapper restores POSTDISPLAY**. Strip the footer before the original saves `orig_postdisplay`. Restore puts back stale footer otherwise.
-   **Widget categories change between versions**. A widget categorized as `modify` in one version may be `clear` in another. Pin zsh-autosuggestions or use version-independent hooks like `zle-line-pre-redraw`.
-   **Ghost plus footer can exceed terminal width**. POSTDISPLAY wraps. Truncate the footer to the remaining width after the ghost.

### region_highlight
-   **Must never run outside zle widget context**. No `2>/dev/null` guards. Only call from widgets and `zle -F -w` callbacks.
-   **Positions come from the current BUFFER**. If a widget changes BUFFER after position computation, highlights point to wrong characters. `zle-line-pre-redraw` catches this.

### Signal handling
-   **Variable name mismatches break cleanup**. TRAPINT sets `_prompt_ctrl_c`. Precmd checks `_prompt_ctrlc`. One underscore kills the path. Keep names in sync.
-   **Precmd runs in signal context after TRAPINT exit**. The precmd hook after Ctrl+C fires with `$?=130` but stays in signal context. Do not call `region_highlight`-modifying functions there.
-   **`zle-line-finish` does not fire on signal exit**. Guarded by `if (done && !errflag)` in `zleread()`. Use `[[ -n $ZLE_LINE_ABORTED ]]` in zle-line-init.
-   **`send-break` does not clear POSTDISPLAY**. Stale footer stays until the next keystroke. Register a wrapper.

### Cursor positioning
-   **printf-based cursor moves assume single-line buffer**. `\033[A\033[%dG` breaks on multiline buffers and narrow terminals. `zle .redisplay` handles wrapping natively.
-   **Blank line on Ctrl+C is geometric**. On a new terminal tab with no scrollback, `\033[2A` clamps to row 1. The cleared footer row becomes a visible blank line. Unavoidable.

### Editing
-   **Esc+Enter must insert `\n`, not `\r`**. `self-insert-unmeta` after ESC inserts raw `\r` (0x0d). Cursor jumps to column 0 on the same line. Bind `LBUFFER+=$'\n'`.
-   **Bracketed-paste and quoted-insert with `\r`**. Pasted text or `^V^M` inserts literal `\r`. Same column-0 corruption. Low priority.
-   **Terminal resize during editing**. Footer uses the old COLUMNS. Shrinking wraps it. Growing leaves a gap. Next Enter fixes it.
