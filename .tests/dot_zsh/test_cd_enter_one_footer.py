#!/usr/bin/env python3
"""
E2E test: cd to chezmoi, press Enter twice. Expect exactly 1 visible footer.

Uses MiniTerm terminal emulator to reconstruct visible screen from raw PTY
output. This detects real stacking: if multiple footers appear on screen,
the test fails.
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
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '24'
        d = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write('source ~/.zshrc 2>/dev/null || true\n')
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)

    time.sleep(1.0); read_all(fd, 0.5)

    # cd to chezmoi
    os.write(fd, f'cd {CHEZMOI}\n'.encode())
    time.sleep(3.0)  # wait for async

    # Press Enter twice
    os.write(fd, b'\n'); time.sleep(1.0)
    os.write(fd, b'\n'); time.sleep(2.0)

    out = read_all(fd, 3.0)

    os.write(fd, b'exit\n'); time.sleep(0.2)
    os.close(fd); os.waitpid(pid, 0)

    # Feed into MiniTerm to reconstruct visible screen
    term = MiniTerm(80, 24)
    term.feed(out)

    # Count footers visible on screen (containing both chezmoi and main)
    n = sum(1 for l in term.display if 'chezmoi' in l and 'main' in l)
    print(f'  Visible footers (MiniTerm): {n}')

    # Dump screen
    for i, l in enumerate(term.display):
        if l.strip():
            print(f'  [{i}] {l[:80]}')

    if n == 1:
        return True, f'exactly {n} visible footer — no stacking'
    elif n == 0:
        return False, 'no footer found'
    else:
        return False, f'{n} footers visible — stacking detected'

if __name__ == '__main__':
    ok, msg = False, 'exception'
    try: ok, msg = run()
    except Exception as e: msg = str(e)
    print(f'  {"PASS" if ok else "FAIL"}: {msg}')
    sys.exit(0 if ok else 1)
