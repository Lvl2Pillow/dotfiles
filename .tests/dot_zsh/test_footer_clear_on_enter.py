#!/usr/bin/env python3
"""
Test: footer is cleared on Enter, not visible during command execution.

After pressing Enter, the previous prompt's footer (marked with `>>`)
should NOT appear in the command output or between output lines.
It should only reappear on the next prompt.
"""
import os, sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_SITE = os.path.join(TEST_DIR, '.venv', 'lib',
                         f'python{sys.version_info.major}.{sys.version_info.minor}',
                         'site-packages')
if os.path.isdir(VENV_SITE):
    sys.path.insert(0, VENV_SITE)

import pty, select, time, re, glob, shutil

PROBE_PATH = os.path.join(TEST_DIR, 'test_prompt_probe.zsh')


def spawn():
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '24'
        os.environ['TERM_PROGRAM'] = ''
        probe_dir = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(probe_dir, exist_ok=True)
        with open(os.path.join(probe_dir, '.zshrc'), 'w') as f:
            with open(PROBE_PATH) as src:
                f.write(src.read())
        with open(os.path.join(probe_dir, '.zshenv'), 'w') as f:
            f.write('# empty\n')
        os.environ['ZDOTDIR'] = probe_dir
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


def cleanup():
    for d in glob.glob('/tmp/zsh_probe_*'):
        shutil.rmtree(d, ignore_errors=True)


def run_test(name, fn):
    cleanup()
    pid, fd = spawn()
    time.sleep(0.8)
    ok, msg = False, 'exception'
    try:
        ok, msg = fn(fd)
    finally:
        try:
            os.write(fd, b'exit\n')
            time.sleep(0.2)
            os.close(fd)
            os.waitpid(pid, 0)
        except Exception:
            pass
        cleanup()
    status = 'PASS' if ok else 'FAIL'
    print(f'[{status}] {name}: {msg}')
    return ok


# ---------- TEST ----------

def test_footer_cleared_on_enter(fd):
    """Footer marker from previous prompt is absent between command output lines.

    When we run: echo A; echo B, the output should be:
        A
        B
    with no '>>' lines between them.
    """
    # Drain initial output
    read_all(fd, 0.5)

    # Send command that produces multiple lines of output
    os.write(fd, b'echo A; echo B\n')
    time.sleep(0.6)
    out = read_all(fd, 0.5)

    # Decode with escape sequences stripped for line analysis
    text = out.decode('utf-8', errors='replace')

    # Split into visible lines (ignore escape sequences, just look at line breaks)
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')

    # Find lines containing command output A and B
    a_lines = [i for i, l in enumerate(lines) if l.strip() == 'A' and 'echo' not in l]
    b_lines = [i for i, l in enumerate(lines) if l.strip() == 'B' and 'echo' not in l]

    if not a_lines:
        return False, 'output line "A" not found'
    if not b_lines:
        return False, 'output line "B" not found'

    # Between A and B lines, there should be no '>>' footer markers
    first_a = a_lines[0]
    first_b = b_lines[0]
    between = lines[first_a:first_b]

    for line in between:
        if '>>' in line and 'echo' not in line and 'zsh' not in line:
            return False, f'footer marker >> found between output lines: {line.strip()}'

    return True, 'no footer between command output lines'


if __name__ == '__main__':
    ok = run_test(test_footer_cleared_on_enter.__doc__, test_footer_cleared_on_enter)
    sys.exit(0 if ok else 1)
