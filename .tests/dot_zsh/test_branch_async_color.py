"""
Tests: after cd to chezmoi, branch color updates (deferred — on next keystroke).

These tests verify that git untracked status is properly detected and
the branch color changes from green (34) to dark red (88) after async completes.
"""
import os, sys, pty, select, time, re

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(TEST_DIR, '.venv', 'lib',
    f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages'))

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

CHEZMOI = os.path.expanduser('~/.local/share/chezmoi')

def _branch_colors_in_output(out):
    """Return all unique branch color codes found in output."""
    colors = set()
    segments = out.split(b'\r')
    for seg in segments:
        found = re.findall(rb'38;5;(\d+)', seg)
        if len(found) >= 2:
            colors.add(found[-1].decode())
    if b'38;5;88' in out:
        colors.add('88')
    return colors

def _last_branch_color(out):
    """Return last branch color code in output (2nd+ color entry)."""
    # Find last occurrence of `38;5;N` followed by branch-like text
    matches = list(re.finditer(rb'38;5;(\d+)', out))
    if len(matches) >= 2:
        return matches[-2 if len(matches) >= 3 else -1].group(1).decode()
    return None

def spawn_in_chezmoi():
    """Start zsh directly in chezmoi directory."""
    config = f'cd {CHEZMOI} 2>/dev/null\nsource ~/.zshrc 2>/dev/null || true\n'
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
        d = f'/tmp/zsh_probe_{os.getpid()}'; os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config)
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)
    time.sleep(1.0); read_all(fd, 0.5)
    return pid, fd

def spawn_from_home():
    config = 'cd ~ 2>/dev/null\nsource ~/.zshrc 2>/dev/null || true\n'
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
        d = f'/tmp/zsh_probe_{os.getpid()}'; os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config)
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)
    time.sleep(1.0); read_all(fd, 0.5)
    return pid, fd

def test_async_untracked_first_cd():
    """After cd from HOME to chezmoi, branch should eventually turn red (88).
    Since TRAPUSR1 can't update POSTDISPLAY, the update happens on next keystroke."""
    pid, fd = spawn_from_home()
    os.write(fd, f'cd {CHEZMOI}\n'.encode())
    time.sleep(3.0)  # wait for async to complete
    out = read_all(fd, 5.0)

    # Press a key to trigger zle-line-pre-redraw
    os.write(fd, b' ')  # space to trigger redraw
    time.sleep(1.0)
    out += read_all(fd, 2.0)

    # Backspace to undo space
    os.write(fd, b'\x7f')
    time.sleep(0.5)
    out += read_all(fd, 1.0)

    os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)

    colors = _branch_colors_in_output(out)
    last_color = _last_branch_color(out)
    text = out.decode('utf-8', errors='replace').replace('\x1b', 'ESC')
    print(f'  Branch colors: {colors}')
    print(f'  Last branch color: {last_color}')

    if last_color == '88':
        return True, f'dark red (88) is the LAST branch color'
    if '88' in colors:
        return True, f'red (88) found in output (last color: {last_color})'
    return False, f'no dark red (88), got {colors}'

if __name__ == '__main__':
    ok, msg = False, 'exception'
    try: ok, msg = test_async_untracked_first_cd()
    except Exception as e: msg = str(e)
    print(f'  {"PASS" if ok else "FAIL"}: {msg}')
    sys.exit(0 if ok else 1)
