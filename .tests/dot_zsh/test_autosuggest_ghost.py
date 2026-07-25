#!/usr/bin/env python3
"""
Red/green test: autosuggestions ghost text appears when typing a command
that matches session history.

Flow:
  1. Start zsh with user's real config (autosuggestions loaded via 01_suggestions.zsh)
  2. Seed in-memory history with 'echo hello'
  3. Type 'echo ' and check for ghost suggestion 'hello'
"""
import os, sys, pty, select, time

LINES = 10


def spawn():
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = str(LINES)
        os.environ['TERM_PROGRAM'] = ''
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)
    return pid, fd


def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r:
            break
        try:
            chunk = os.read(fd, 8192)
            if not chunk:
                break
            out += chunk
        except OSError:
            break
    return out


def run_test():
    pid, fd = spawn()
    time.sleep(0.8)
    read_all(fd, 0.5)
    read_all(fd, 0.3)

    # Seed history: run 'echo hello'
    os.write(fd, b'echo hello\n')
    time.sleep(0.5)
    read_all(fd, 0.3)

    # Type 'echo ' — should trigger autosuggestions
    os.write(fd, b'echo ')
    time.sleep(0.5)
    out2 = read_all(fd, 0.3)

    text = out2.decode('utf-8', errors='replace')
    print(f"  Output after typing 'echo ': {text[-200:]!r}")

    if 'hello' not in text:
        print("  [FAIL] Ghost text 'hello' not found")
        return False

    print("  [PASS] Ghost text 'hello' found")
    return True


def cleanup():
    pass


if __name__ == '__main__':
    try:
        ok = run_test()
        status = 'PASS' if ok else 'FAIL'
        print(f'[{status}] Autosuggestions ghost text appears when typing')
        sys.exit(0 if ok else 1)
    except Exception as e:
        print(f'[FAIL] Exception: {e}')
        sys.exit(1)
    finally:
        cleanup()
