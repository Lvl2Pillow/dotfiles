# handoff: zsh prompt footer below input line

## Goal

Show a minimal `%` prompt on the input line while displaying full directory/git
info as a colored footer that stays visible when the input buffer wraps onto
multiple lines.

## What was tried

| Approach | Colors | Survives wrap | Notes |
|---|---|---|---|
| `sc/rc` in `PROMPT` | ✅ | ❌ | Colored footer on line 2; overwritten when input wraps. Current restored backup behavior. |
| `zle -M` with ANSI | ❌ | ✅ | zsh sends codes to terminal, but macOS Terminal.app displays them literally (`^[[38;5;135m...`). No colors. |
| `zle -M` plain text | ❌ | ✅ | Dynamic positioning works, but no colors. |
| Dynamic cursor-down in `PROMPT` | ✅ | ❌ | Footer moves down via `\e[NB`, but terminal scrolls at bottom and corrupts display. |
| Deferred `zle -F` callback | ✅ | ❌ | Renders footer after zle redraw, but interleaves with zle output and corrupts. |
| `POSTDISPLAY` + `region_highlight` | ✅ | ❌ | Colored text follows cursor, but sits on the same line as the wrapped input, not on a fresh line below. |
| DECSTBM scroll region | ✅ | ✅ | Reserves bottom terminal line for footer; input wraps above it. Works in pyte tests and macOS Terminal.app. |

## Working solution: DECSTBM scroll region

`/Users/lvl2pillow/.zsh/05_prompt.zsh.exp` contains the experimental implementation.

On every prompt:
1. Sets scroll region to lines `1..LINES-1` with `\e[1;Nr`.
2. Moves cursor to bottom line `\e[LINES;1H`, clears it, and prints the colored footer.
3. Moves cursor back to `\e[1;1H` and prints the minimal `%` prompt.
4. Zle renders the input buffer within the scroll region, so wrapping never touches the footer line.

`preexec` resets the scroll region (`\e[r`) before command output so normal full-screen output works.

### Trade-offs

- Footer is pinned to the **bottom** of the terminal, not directly below the prompt.
- Terminal must support DECSTBM (macOS Terminal.app, iTerm2, Alacritty, xterm do).
- Resizing the terminal while editing may briefly misplace the footer until the next prompt.

## Test harness

Preserved in `/Users/lvl2pillow/.local/share/chezmoi/.tests/dot_zsh/`:

- `test_prompt_footer.py` — pty-based red/green tests using `pyte` terminal emulator.
- `.venv/` — virtualenv with `pyte` installed.

Run:

```zsh
cd /Users/lvl2pillow/.local/share/chezmoi/.tests/dot_zsh
.venv/bin/python test_prompt_footer.py
```

### Current test results

Against the restored original `~/.zsh/05_prompt.zsh`:

```
[PASS] Footer below prompt is colored for short input.
[FAIL] When buffer wraps, footer stays at bottom and buffer stays above it.
[FAIL] A long wrapping buffer does not overwrite the bottom footer.
[PASS] Footer text should not show literal escape sequences.
[PASS] After pressing Enter, command output uses full screen.
```

Against the experimental `~/.zsh/05_prompt.zsh.exp`:

```
[PASS] Footer below prompt is colored for short input.
[PASS] When buffer wraps, footer stays at bottom and buffer stays above it.
[PASS] A long wrapping buffer does not overwrite the bottom footer.
[PASS] Footer text should not show literal escape sequences.
[PASS] After pressing Enter, command output uses full screen.
```

## File state

- `~/.zsh/05_prompt.zsh` — restored original (colored footer, overwritten on wrap).
- `~/.zsh/05_prompt.zsh.exp` — experimental DECSTBM version (colored footer pinned at bottom, survives wrapping).
- `~/.zsh/05_prompt.zsh.bak` — no longer exists; backup was renamed to `.exp`.

## References

- Unix StackExchange: [Display stuff below the prompt at a shell prompt](https://unix.stackexchange.com/q/1022)
- Powerlevel10k source: `~/Documents/powerlevel10k/internal/p10k.zsh`
- pi TUI bottom-pinning: flat differential re-render (not applicable to zsh)

## Decision needed

Choose which `05_prompt.zsh` to keep:
1. **Original** (`05_prompt.zsh`) — colors, simple, footer overwritten on wrap.
2. **Experimental** (`05_prompt.zsh.exp`) — colors, footer pinned at bottom, survives wrap, slightly unusual layout.
3. **Powerlevel10k** — does not natively support a footer below the input line; would need custom work.
