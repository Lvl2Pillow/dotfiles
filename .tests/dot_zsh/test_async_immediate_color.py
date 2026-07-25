#!/usr/bin/env python3
"""
RED test: git status colors should appear immediately after async completes,
without requiring an extra keystroke.

The zle -F callback updates region_highlight and calls zle .redisplay.
This test verifies the colors are rendered BEFORE any key is pressed.

Currently fails (RED) because zle .redisplay doesn't trigger the
zrefresh() pipeline that re-applies region_highlight from a zle -F handler.
"""
import os, sys, pty, select, time, re

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(TEST_DIR, '.venv', 'lib',
    f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages'))

CHEZMOI = os.path.expanduser('~/.local/share/chezmoi')


def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r:
            break
        try:
            c = os.read(fd, 8192)
            out += c
        except:
            break
    return out


def branch_colors_in_output(out):
    """Return all unique branch color codes found in output."""
    colors = set()
    found = re.findall(rb'38;5;(\d+)', out)
    for c in found:
        colors.add(c.decode())
    return colors


def test_immediate_color_after_cd():
    """
    cd into chezmoi, wait for async to complete, check for dirty color
    BEFORE pressing any key.
    """
    config = f'cd ~ 2>/dev/null\nsource ~/.zshrc 2>/dev/null || true\n'
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '24'
        d = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write(config)
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)

    time.sleep(1.0)
    read_all(fd, 0.5)

    # cd into chezmoi (has untracked/staged changes)
    os.write(fd, f'cd {CHEZMOI}\n'.encode())
    time.sleep(0.2)

    # Wait for async to complete (3s safety margin)
    time.sleep(3.0)

    # Capture ALL output since cd — includes prompt + any zle .redisplay sequences
    out = read_all(fd, 1.0)

    os.write(fd, b'exit\n')
    time.sleep(0.2)
    os.close(fd)
    os.waitpid(pid, 0)

    colors = branch_colors_in_output(out)
    text = out.decode('utf-8', errors='replace').replace('\x1b', 'ESC')
    print(f'  Colors: {colors}')
    tail = text[-300:]
    print(f'  Tail: {tail}')

    if '88' in colors:
        return True, f'dark red (88) in output: {colors}'
    return False, f'no dark red (88), only: {colors}'


if __name__ == '__main__':
    ok, msg = False, 'exception'
    try:
        ok, msg = test_immediate_color_after_cd()
    except Exception as e:
        msg = str(e)
    print(f'  {"PASS" if ok else "FAIL"}: {msg}')
    sys.exit(0 if ok else 1)
