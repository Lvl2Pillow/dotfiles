# Testing e2e Prompt Behavior

Test zsh prompt features through a real terminal. Not through mocks, not through function calls, not through simulations that bypass zle. Only a real zsh process with a real PTY can tell you if the prompt works.

## Bad Tests

Tests that let you fake success. They pass for the wrong reasons — your code still breaks under a real shell.

- **Mocking zle functions.** Substituting `zle` calls with no-ops or stubs hides every real problem. You never see that `region_highlight` doesn't render, that POSTDISPLAY doesn't clear on signal exit, that autosuggest wrappers never fire.
- **Calling prompt functions directly.** Running `_prompt_precmd` in a unit test tells you nothing. The test passes, but the prompt still breaks — the function was never called from zle context, `region_highlight` was never in scope, the widget dispatch never happened.
- **Subprocess with fake `.zshrc`.** Running `zsh -c 'source prompt.zsh; ...'` skips the interactive machinery. No zle-line-init, no zle -F, no autosuggest hooks, no signal delivery. Your test passes. Your prompt still has the bug.
- **Checking internal variables instead of terminal output.** Asserting `_prompt_git_untracked=1` proves nothing. The user sees colors on screen, not global variables. The variable might be set correctly but `region_highlight` might not render it.
- **Simulating terminal output.** Writing expected escape sequences into a string and comparing against your own code's output tests nothing. You trained the test on the buggy output. The test passes because both sides agree on the wrong answer.
- **Too-short timeouts.** Sleeping 50ms for async to complete means your test only passes when the machine is fast. On a slow machine, the async hasn't finished, the test checks stale state, and passes for the wrong reason. The real bug waits until the async completes.

## Good Tests

Tests that force you to reproduce the real environment. They hurt. They're slow. They catch bugs.

- **PTY-based.** Fork a real zsh with `pty.fork()`. The child runs a full interactive shell. The parent sends keystrokes and reads terminal output. This is the only way to exercise the zle event loop, widget dispatch, signal delivery, and terminal rendering.
- **Load the real config.** The test's `.zshrc` sources `05_prompt.zsh` (and any dependencies). Not a synthetic subset. The exact same code the user runs.
- **Exercise zle widgets by sending keystrokes.** `os.write(fd, b': true\n')` triggers accept-line through the real widget dispatch. Not through calling `_prompt_zle_accept_line` directly. The distinction matters because the autosuggest wrapper runs between the keystroke and the widget.
- **Check terminal output, not internal state.** Scan `os.read(fd, ...)` output for color escape codes, text content, cursor positioning sequences. A correct test asserts on what the user sees.
- **Wait realistically for async.** 3 seconds minimum. Async involves a fork, git filesystem scan, FIFO write, and zle -F callback. On a loaded machine, that takes time. A test that doesn't wait long enough passes when the async hasn't fired yet.
- **Test real workflows.** Enter a command. Press Ctrl+C. cd to another directory. Press Alt+A (accept-and-hold). Type text past the terminal width. Each is a distinct user action with distinct zle dispatch behavior. Test them.
- **Red-green cycle.** Write the test first. Confirm it fails. Then fix the code. Confirm the test passes. A test that never failed doesn't test anything.

## Essential Utilities

You need a few helpers. Keep them minimal. Every abstraction between the test and the terminal is a chance to leak the real behavior.

```python
import os, sys, pty, select, time, re

def read_all(fd, timeout=0.5):
    """Read all available data from a PTY fd within a timeout."""
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r:
            break
        try:
            out += os.read(fd, 8192)
        except:
            break
    return out
```

```python
def spawn_zsh(config_lines):
    """Fork a real zsh with given .zshrc lines. Returns (pid, fd)."""
    config = '\n'.join(config_lines) + '\n'
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '24'
        d = f'/tmp/zsh_test_{os.getpid()}'
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write(config)
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)
    time.sleep(1.0)
    read_all(fd, 0.5)
    return pid, fd
```

```python
def branch_colors_in_output(out):
    """Return set of color codes from terminal output."""
    return {c.decode() for c in re.findall(rb'38;5;(\d+)', out)}
```

```python
# Cleanup — must reap child
os.write(fd, b'exit\n')
time.sleep(0.2)
os.close(fd)
os.waitpid(pid, 0)
```

## What to Test

Each category maps to a real user experience failure:

| Category | What breaks | What to check |
|----------|-------------|---------------|
| Color accuracy | Stale repo shows green | After async completes in a dirty repo, output contains 38;5;88 (dark red) |
| Footer cleanup | Stale text after Enter | After `: true\n`, output does not contain old branch text |
| Signal cleanup | Blank line after Ctrl+C | After Ctrl+C, output does not contain extra blank line |
| Autosuggest ghost | Ghost text covers footer | After typing prefix with suggestion, both ghost and footer visible |
| Accept-and-hold | Footer persists after Alt+A | After `: true` + Alt+A, output does not contain stale footer line |
| Wrapping | Footer garbled on wide buffer | Type 60 chars, footer renders below prompt (not overlapping) |
| Async update | Colors don't update without keystroke | After cd + async wait, output contains correct color BEFORE any key |
