#!/usr/bin/env python3
"""
RED tests for:
1. Ctrl+C should show red % symbol (error exit code)
2. Async git untracked should update branch color on first prompt after cd
"""
import os, sys, pty, select, time, re

TEST_DIR = os.path.dirname(os.path.abspath(__file__))

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

def spawn_real(config='source ~/.zshrc 2>/dev/null || true', lines=24):
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'; os.environ['LINES'] = str(lines)
        d = f'/tmp/zsh_rtest_{os.getpid()}'; os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config + '\n')
        with open(os.path.join(d, '.zshenv'), 'w') as f: f.write('export ZDOTDIR="$HOME"\n')
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)
    return pid, fd

pass_count = 0
fail_count = 0
CHEZMOI_DIR = os.path.expanduser('~/.local/share/chezmoi')

def test(fn):
    global pass_count, fail_count
    name = fn.__doc__.strip() if fn.__doc__ else fn.__name__
    ok, msg = False, 'exception'
    try: ok, msg = fn()
    except Exception as e: msg = str(e)
    if ok: pass_count += 1; print(f'  PASS: {name}')
    else: fail_count += 1; print(f'  FAIL: {name} — {msg}')

# ===== Bug 1: Ctrl+C should show red % =====

def _red_ctrlc_symbol():
    """Ctrl+C should produce red % symbol (ANSI 196)."""
    pid, fd = spawn_real(lines=10)
    time.sleep(0.8); read_all(fd, 0.5)

    os.write(fd, b'\x03')
    # Wait longer for TRAPINT + .reset-prompt to complete
    out = read_all(fd, 2.0)

    pct_idx = out.rfind(b'%')
    if pct_idx < 0:
        os.close(fd); os.waitpid(pid, 0)
        return False, '% not found in output'

    prefix = out[max(0, pct_idx-80):pct_idx]
    colors = re.findall(rb'\x1b\[([0-9;]*)m', prefix)
    has_red = any(b'38;5;196' in c or c == b'91' or c == b'101' for c in colors)

    os.close(fd); os.waitpid(pid, 0)
    if not has_red:
        return False, f'no red ANSI before %: {[c.decode() for c in colors]}'
    return True, '% is red'

# ===== Bug 2: Async git untracked on first cd =====

def _async_untracked_first_cd():
    """After cd to chezmoi, branch turns red (88) after async completes."""
    if not os.path.isdir(CHEZMOI_DIR):
        return False, f'chezmoi dir not found: {CHEZMOI_DIR}'

    pid, fd = spawn_real(lines=24)
    time.sleep(0.8); read_all(fd, 0.5)

    # cd to chezmoi — capture ALL output after this command
    os.write(fd, f'cd {CHEZMOI_DIR}\n'.encode())
    # Wait long enough for cd + precmd + async + TRAPUSR1 + redraw
    out = read_all(fd, 8.0)

    # Split by newline on raw bytes
    lines = out.split(b'\n')

    # Check for dark red anywhere in raw bytes
    has_dark_red_anywhere = b'38;5;88' in out

    # Check LAST occurrence of branch footer
    # Footer lines have pattern: ESC[... path ESC[... branch ESC[...
    last_branch_color = None
    for l in lines:
        colors = re.findall(rb'\x1b\[38;5;(\d+)m', l)
        if len(colors) >= 2 and b'/' in l and b' ' in l:
            last_branch_color = colors[-1].decode()

    os.close(fd); os.waitpid(pid, 0)

    if not has_dark_red_anywhere:
        return False, f'dark red (88) not found anywhere in output'

    if last_branch_color != '88':
        return False, f'last branch color is {last_branch_color}, expected 88 (dark red)'

    return True, 'branch is red (88) after async'

def main():
    print('RED tests: Ctrl+C red % + async untracked')
    for fn in [_red_ctrlc_symbol, _async_untracked_first_cd]:
        test(fn)
    print(f'\n{pass_count}/{pass_count + fail_count} passed')
    sys.exit(0 if fail_count == 0 else 1)

if __name__ == '__main__':
    main()
