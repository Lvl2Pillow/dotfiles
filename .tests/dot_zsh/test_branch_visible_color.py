#!/usr/bin/env python3
"""
RED test: after cd (from non-git dir) → async, visible branch color
should be red (88) for untracked files, not green (34).

Starts PTY at /tmp (non-git) so we see the fresh green→red transition.
Uses MiniTerm color tracking for terminal-accurate visible color.
"""
import os, sys, pty, select, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.venv', 'lib',
    f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages'))
from miniterm import MiniTerm

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

def run():
    CHEZMOI = os.path.expanduser('~/.local/share/chezmoi')
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir('/tmp')  # start in a non-git directory
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '24'
        d = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write('source ~/.zshrc 2>/dev/null || true\n')
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)

    time.sleep(1.0); read_all(fd, 0.3)

    # cd to chezmoi — triggers git detection in a fresh repo context
    os.write(fd, f'cd {CHEZMOI}\n'.encode())
    time.sleep(3.5)  # wait for async + TRAPUSR1

    out = read_all(fd, 5.0)

    os.write(fd, b'exit\n'); time.sleep(0.2)
    os.close(fd); os.waitpid(pid, 0)

    # Feed through MiniTerm with color tracking
    term = MiniTerm(80, 24)
    term.feed(out)

    print('  --- visible screen ---')
    term.dump(with_color=True)

    # Print footer rows with per-char fg
    for r in range(term.rows):
        line = term._grid[r]
        chars = ''.join(cell['ch'] for cell in line).rstrip()
        if not chars:
            continue
        fg_list = []
        for c in range(min(len(chars)+5, term.cols)):
            cell = line[c]
            if cell['ch'] != ' ':
                fg_list.append((cell['ch'], cell['fg']))
        print(f'  Row {r}: {chars}')
        print(f'    fgs: {[(ch, fg) for ch, fg in fg_list if fg >= 0 or ch in "main"]}')

    # Find 'main' on screen and check its color
    result = term.color_at_text('main')
    if result is None:
        print('  main not found on screen')
        return False, 'main not visible'

    r, c, fg = result
    print(f'  main at row {r}, col {c}, fg color {fg}')

    # Regardless of whether chezmoi has untracked files RIGHT NOW,
    # on the user's real terminal it DOES — so this test should detect
    # the bug where color is NOT red.
    # If the test passes (shows red), then MiniTerm doesn't reproduce
    # the real terminal behavior and we need to adjust.
    if fg == 88:
        return True, f'visible main is correct red (88)'
    elif fg == 34:
        return False, f'visible main is GREEN (34) — bug!'
    elif fg == -1:
        return False, f'visible main has DEFAULT color (-1) — no SGR applied'
    else:
        return False, f'visible main has unexpected fg {fg} (expected 88)'

if __name__ == '__main__':
    ok, msg = False, 'exception'
    try: ok, msg = run()
    except Exception as e: msg = str(e)
    print(f'  {"PASS" if ok else "FAIL"}: {msg}')
    sys.exit(0 if ok else 1)
