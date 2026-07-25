# Prompt Architecture

## Footer Design

Two-line prompt: symbol on line 1 (`% ` or `# `), directory/git on line 2 (footer).

No `RPROMPT` or `PROMPT2` manipulation. Footer lives in `POSTDISPLAY`:
```
POSTDISPLAY = <ghost_text>\n<prompt_text>
```

## Color System

- `_prompt_rh_colors` array set by `_prompt_precmd` (unconditionally, even during async)
- `region_highlight` entries applied by `_prompt_zle_append_footer` (zle widget context only)
- Branch colors: 34=green(clean), 88=darkred(untracked), 208=orange(unstaged), 220=yellow(staged), 112=lime(stashed)

## Async Update Flow (TRAPUSR1)

```
USR1 signal → TRAPUSR1
  → _prompt_precmd (updates _prompt_rh_colors, _prompt, etc.)
  → printf writes footer with current _prompt_rh_colors
  → printf \033[A\033[%dG repositions cursor to after "% " (no zle involvement)
```

No `.reset-prompt` in TRAPUSR1 — avoids `region_highlight` desync and stale redraw.

## Cursor Fix (TRAPUSR1)

After TRAPUSR1 printf writes footer (row below prompt), cursor is at end of footer text.
Move cursor to correct position with: `\033[A\033[%dG` (up one row, absolute column N).
Where N = 3 + ${#BUFFER} (after `% ` and any typed text).

## Key Widgets

- `accept-line`: `POSTDISPLAY=` → `zle .accept-line`. No `zle -R` (redundant — `.accept-line` calls `zrefresh()` internally). No saved-original if/else (autosuggest's clear wrapper's `POSTDISPLAY=` is redundant with ours).
- `esc-enter-newline`: Binding `^[^M` → custom widget → `LBUFFER+=$'\n'`. Replaces default `self-insert-unmeta` which inserted `\r` (carriage return) — caused cursor column-0 corruption and blank lines.
- `zle-line-init`: calls `_prompt_zle_append_footer` to append footer + region_highlight.
- `_zsh_autosuggest_highlight_apply` wrapper: calls `_prompt_zle_append_footer` after autosuggest applies ghost.

### Autosuggest Widget Wrappers

Autosuggest categorizes widgets into 5 actions via `_zsh_autosuggest_bind_widgets`:

| Action | Default widgets | POSTDISPLAY handling | done=1?
|--------|----------------|---------------------|--------
| `clear` | `accept-line`, history-search*, up/down-line-or-*, etc. | `POSTDISPLAY=` before original | Yes (accept-line only)
| `accept` | `forward-char`, `end-of-line`, vi-* variants | Appends ghost to BUFFER, then `POSTDISPLAY=` | No
| `execute` | (none by default) | Appends ghost to BUFFER, calls accept-line | Yes
| `partial_accept` | `forward-word`, vi-* variants | Moves word from ghost to BUFFER | No
| `modify` | **Everything else** (includes accept-and-hold, self-insert, etc.) | Saves POSTDISPLAY → clears → calls widget → **restores POSTDISPLAY** | Yes (accept-and-hold etc.)

**Four overrides** strip the prompt footer from POSTDISPLAY before autosuggest processes it:

```
_zsh_autosuggest_accept:        Ctrl+E / → at end  — strip footer, accept ghost → buffer
_zsh_autosuggest_partial_accept: Alt+F / Ctrl+F    — strip footer, move word → buffer
_zsh_autosuggest_execute:       Ctrl+O              — strip footer, accept → submit
_zsh_autosuggest_modify:        (all modify widgets) — strip footer when WIDGET=*accept-*
```

All: `[[ $WIDGET = *accept-* ]] && POSTDISPLAY="${POSTDISPLAY%%$'\n'*}"` then call original.

The `modify` override is conditional (`[[ $WIDGET = *accept-* ]]`) so normal typing (self-insert, etc.) preserves the footer.

## Ctrl+C Signal Handling

### Key insight: send-break widget is dead code for Ctrl+C

Ctrl+C is the terminal's INTR character (`stty intr ^C`). The terminal driver sends **SIGINT** directly — byte 0x03 never enters zle's input buffer. zle never dispatches `send-break` widget.

```
Ctrl+C → terminal driver → SIGINT → zsh → TRAPINT (if defined)
                                       → zle aborts (if TRAPINT returns non-zero)
                                       → send-break widget NEVER dispatches
```

`send-break` widget wrapper was removed from the prompt file — it was dead code for interactive Ctrl+C.

### TRAPINT flow

```
TRAPINT returns non-zero (130)
  → dotrapargs() sets errflag |= ERRFLAG_INT, lastval=130
  → zlecore() loop exits (while !done && !errflag && !exit_pending)
  → zleread() calls trashzle()
      → trashedzle=1
      → zrefresh()        (see below)
      → moveto(nlnct, 0)  (see below)
      → tcout(TCCLEAREOD) if clearflag
      → postedit output
      → settyinfo()       (restore cooked mode)
  → zleread() returns NULL
  → loop() calls preprompt() → precmd hooks run with $?=130
  → parse_event() → ingetcline() → zleentry(ZLE_CMD_READ) → zleread() → zle-line-init → zrefresh()
```

### trashzle's zrefresh() behavior

- Called with `trashedzle=1`
- If `!clearflag`: calls `reexpandprompt()` (re-expands PROMPT from prompt escapes)
- **POSTDISPLAY rendered unconditionally** — no `trashedzle` guard (only right prompt has one, via `TRANSIENTRPROMPT`)
- `nlnct = rpms.ln + 1` after zrefresh — counts ALL rendered lines including POSTDISPLAY
- `resetvideo()` is NOT called unless `resetneeded` was already set (rare)

### moveto(nlnct, 0) — the newline source

`trashzle()` calls `moveto(nlnct, 0)` to position cursor at the line AFTER the displayed content.

- On xterm-256color, `TCDOWN` (`cud1=^J=\n`) is **disabled** at init (zsh overrides it because it's just `\n`)
- Falls through to `\r` + one `\n` per line of downward movement
- Number of `\n` = nlnct - vln (target line minus current video line)
- For a 2-line display (prompt + footer): vln=0, nlnct=2 → **two `\n`**

### zline-line-finish does NOT fire on signal exit

From `zleread()`:
```c
if (done && !exit_pending && !errflag)
    zlecallhook(finish, NULL);  // finish = "zle-line-finish"
```
- `accept-line`: done=1, errflag=0 → **fires**
- `send-break` / SIGINT: errflag is set → **skipped**
- Workaround: test `[[ -n $ZLE_LINE_ABORTED ]]` in `zle-line-init` to detect aborted state.

## The Blank Line Problem

### Source of the blank line after Ctrl+C

After TRAPINT's printf clears the footer and moves cursor, trashzle runs:

```
1. zrefresh() — computes display diff: POSTDISPLAY unchanged (zle's model),
                no terminal output (no diff from zle's perspective).
                But physically, footer line was cleared by printf.

2. moveto(nlnct=2, 0):
   - zle model: vln=0 (cursor on prompt line 0)
   - target: line 2 (one past the end of the 2-line display)
   - outputs: two \n → cursor moves 2 rows down
   - Physical cursor: Row 1 (prompt) → \n → Row 2 (cleared footer) → \n → Row 3

3. New prompt draws at Row 3.
   Row 2 is now a visible blank line.
```

### Why `\033[2A` vs `\033[A` matters

- `\033[A` (up 1): cursor to Row 1 (prompt). moveto's two `\n` → Row 3. Blank line at Row 2.
- `\033[2A` (up 2) on non-new-tab: Row 0 exists in scrollback, cursor goes to Row 0. moveto's two `\n` → Row 2 (where cleared footer was). New prompt overwrites Row 2. No blank line.
- `\033[2A` on new tab: Row 0 doesn't exist → clamped at Row 1. Same as `\033[A`. Blank line.

**Geometric inevitability**: On a new tab, there's no row above the prompt to absorb the extra row. The cleared footer row becomes a visible blank line.

### Solutions considered

| Approach | New tab | Existing prompt |
|---|---|---|
| `\033[1B\033[2K\033[2A` (old) | Blank line | Works |
| `\033[1B\033[2K\033[A` (up 1) | Blank line | Blank line |
| `\033[1B\033[2A` (don't clear footer) | Old footer visible | Works (new prompt overwrites footer) |
| `\033[A` in PROMPT via `%{...%}` | Works (prompt moves up) | Pulls prompt up unnecessarily |
| Detectable `_prompt_ctrlc` flag | Conditional `\033[A` in PROMPT | No-op when flag not set |

## TRAPUSR1 vs zle context

- `region_highlight` modification in signal context: **does NOT abort the handler** (all probes succeeded without error), but the function is never called in TRAPUSR1.
- `_prompt_zle_append_footer` is only called from zle widget context (`zle-line-init`, `zle-line-pre-redraw`, autosuggest highlight wrapper).
- TRAPUSR1 uses `printf` directly because:
  1. `.reset-prompt` applies stale `region_highlight` (color fight)
  2. `zle` functions are unsafe in signal context
  3. `printf` is a direct terminal write — no zle state dependency

## Known Constraints

### Region_highlight
- `region_highlight` modification may silently fail outside zle widget dispatch (wrapped in `{ } 2>/dev/null`). `_prompt_rh_positions` is cleared unconditionally, so lost position tracking causes duplicate entries on next successful call.
- Cleanup pattern `"${(@)region_highlight:#${pos} *}"` removes entries matching start/end positions. Safe — won't match autosuggest's ghost highlight (different positions). Won't match other positions with same start but different end because pattern includes trailing space + `*`.

### Buffer width assumptions
- `\033[A\033[%dG` cursor fix (TRAPUSR1) assumes buffer doesn't wrap to next line. For buffers wider than terminal, cursor ends up on wrong row.
- `target_col = 3 + ${#BUFFER}` counts ALL characters including newlines. Multiline buffer (from pasting, `\n` insertion, or breaking with `\r`?) produces a wrong column number — may exceed terminal width or land on wrong row.

### Ctrl+C variable name mismatch
- TRAPINT sets `_prompt_ctrl_c=1` (with underscore before `c`). Precmd checks `_prompt_ctrlc` (no underscore). The `printf '\033[A\033[2K'` cleanup in precmd never fires. Old footer persists until next keystroke. **Must unify variable names.**

### Autosuggest clear widget stale region_highlight
- Autosuggest categorizes widgets as "clear", "accept", "execute", "partial_accept", or "modify" (catch-all).
- Our `_prompt_zle_append_footer` runs inside `_zsh_autosuggest_highlight_apply`, which is called BEFORE the original widget is invoked for "clear" category widgets.
- "Clear" widgets include: `up-line-or-history`, `down-line-or-history`, all history-search variants, and others. These CHANGE `$BUFFER`.
- Our region_highlight positions are computed from the OLD buffer, then the widget changes the buffer. Positions become stale until next keystroke.
- Fix: `_prompt_zle_append_footer` must run AFTER the original widget, not before. Options:
  - Replace autosuggest clear wrappers with our own
  - Use `zle-line-pre-redraw` hook as safety net (fires after every widget completes)

### send-break (^G) stale footer
- `^G` is bound to `send-break`. No custom wrapper exists in current prompt.
- Built-in `send-break` does NOT clear POSTDISPLAY. After `^G`, footer text persists on screen even though the buffer was cleared.
- Next keystroke triggers `_prompt_zle_append_footer` via autosuggest → correct footer is set. But between `^G` and next keystroke, stale footer is visible.
- Fix: register `zle -N send-break` with `POSTDISPLAY=; zle .send-break`.

### Autosuggest dependency
- Footer re-triggers on every keystroke ONLY through autosuggest's widget-wrapping mechanism (`_zsh_autosuggest_highlight_apply` → our hook → `_prompt_zle_append_footer`).
- If autosuggest is disabled, removed, or its wrapping fails, footer is only set once per command (via `zle-line-init`). Subsequent keystrokes change `$BUFFER` but region_highlight positions stay stale.
- Fix: register `zle-line-pre-redraw` hook that calls `_prompt_zle_append_footer`. Autosuggest doesn't hook this (only `zle-line-init`), so it's redundant when autosuggest works (every widget triggers `zle -R` → zrefresh → `zle-line-pre-redraw`), but provides a safety net when it doesn't.

### Bracketed-paste and quoted-insert literal `\r`
- `bracketed-paste` inserts pasted data literally via `.self-insert`. If data contains `\r` (0x0d), cursor goes to column 0 on same line — same class of corruption as the original Esc+Enter `self-insert-unmeta` bug.
- `quoted-insert` (`^V`) followed by `^M` also inserts literal `\r`.
- Fixing would require wrapping these widgets to sanitize `\r`, which changes explicit user intent. Low priority — `\r` rarely appears in pasted text or typed input.

### Terminal resize during editing
- `_prompt_precmd` recomputes truncation using `COLUMNS`, but only runs once per command (not during editing).
- Between keystrokes, if terminal width changes, footer text was sized for old width. Shrinking truncates via zle's natural line wrapping; growing leaves unused space.
- TRAPUSR1 printf clears the entire line before writing footer, so text is always full-width. But `target_col` for cursor reposition might exceed new terminal width — cursor wraps or lands on wrong row.
- Fix: cap `target_col` at `COLUMNS - 1` in TRAPUSR1, or use relative cursor positioning instead of absolute column.

### `^[^[` (Esc Esc) bound to undefined-key
- `^[^[` is `undefined-key` — beeps and does nothing. Not `send-break` as might be expected.
- This is a configuration choice, not a bug.

### Esc+Enter (\033\r) → self-insert-unmeta inserts \r
- **FIXED**: Custom widget `_prompt_esc_enter_newline` binds `^[^M` to `LBUFFER+=$'\n'`, replacing `self-insert-unmeta` which inserted `\r`.
- `\n` (0x0a) creates proper multiline buffer. `\r` (0x0d) caused cursor column-0 corruption.
- `\r` vs `\n` distinction is byte-level — both `^M` and `^J` trigger `accept-line` when pressed alone, but `self-insert-unmeta` inserts the raw byte after ESC.

### IS_MANAGED chezmoi fast path
- Skips untracked file detection — branch stays green even with untracked files. Design choice for chezmoi repos.

### POSTDISPLAY= in signal context
- `POSTDISPLAY=` assignment is safe in TRAPINT (signal context), but does NOT prevent trashzle's `zrefresh()` from rendering POSTDISPLAY — zrefresh uses a buffer-level copy of the POSTDISPLAY content, not the variable read at render time. To actually prevent footer redraw during trashzle, the POSTDISPLAY must be cleared before the signal handler returns (which is impossible to guarantee across all zsh versions).
- `zle -R` does NOT trigger a `zrefresh()` on signal exit — `trashzle()` calls `zrefresh()` directly regardless of dirty flag.
