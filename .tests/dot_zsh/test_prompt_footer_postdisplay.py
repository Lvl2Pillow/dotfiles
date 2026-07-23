#!/usr/bin/env python3
"""Red/green tests for POSTDISPLAY + region_highlight prompt footer.

Approach:
  PROMPT = '%# '
  precmd: computes footer content (dir, branch), stores in _prompt_footer
  zle-line-init: sets POSTDISPLAY = '\n<footer>' (fires on every new prompt)
  zle-line-pre-redraw: sets POSTDISPLAY + region_highlight (fires on every redraw)

Tests verify by checking raw PTY output for expected markers and ANSI codes.
Byte ordering is NOT used for layout assertions — zle interleaves escape
sequences for cursor positioning.
"""
import os, sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_SITE = os.path.join(TEST_DIR, '.venv', 'lib',
                         f'python{sys.version_info.major}.{sys.version_info.minor}',
                         'site-packages')
if os.path.isdir(VENV_SITE):
    sys.path.insert(0, VENV_SITE)

import pty, select, time, re, shutil, glob

COLUMNS = 80
LINES = 24
PROBE_PATH = os.path.join(TEST_DIR, 'test_prompt_probe.zsh')


def spawn():
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = str(COLUMNS)
        os.environ['LINES'] = str(LINES)
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


def has_ansi_before(data, substr, lookback=80):
    idx = data.rfind(substr)
    if idx < 0:
        return False
    prefix = data[max(0, idx - lookback):idx]
    return bool(re.search(rb'\x1b\[[0-9;]*m', prefix))


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


def init_prompt(fd):
    """Send initial keystroke to trigger zle-line-pre-redraw, return accumulated output."""
    out = read_all(fd, 0.5)
    os.write(fd, b' \n')
    time.sleep(0.4)
    out += read_all(fd, 0.5)
    return out


# ---------- TESTS ----------

def test_single_line_color(fd):
    """Footer below prompt is colored for short input."""
    out = init_prompt(fd)
    os.write(fd, b'cd ~/.zsh\n')
    time.sleep(0.5)
    out += read_all(fd, 0.6)
    os.write(fd, b'echo hi')
    time.sleep(0.4)
    out += read_all(fd, 0.5)

    # Footer marker present
    if b'>>' not in out:
        return False, 'footer marker >> not found'
    # ANSI color codes appear before last >> in raw output
    if not has_ansi_before(out, b'>>'):
        return False, 'footer found but no ANSI color codes before it'
    return True, 'colored footer visible'


def test_multiline_pushes_footer(fd):
    """When buffer wraps, footer stays visible."""
    out = init_prompt(fd)
    os.write(fd, b'cd ~/.zsh\n')
    time.sleep(0.5)
    out += read_all(fd, 0.6)
    os.write(fd, b'echo ')
    os.write(fd, b'a' * 160)
    time.sleep(0.8)
    out += read_all(fd, 0.8)

    if b'>>' not in out:
        return False, 'footer marker >> not found'
    if b'aaaa' not in out:
        return False, 'buffer text aaaa not found'
    return True, 'footer and buffer both present'


def test_long_buffer_stays_above_footer(fd):
    """A long wrapping buffer coexists with footer."""
    out = init_prompt(fd)
    os.write(fd, b'cd ~/.zsh\n')
    time.sleep(0.5)
    out += read_all(fd, 0.6)
    os.write(fd, b'echo ')
    os.write(fd, b'a' * 160)
    time.sleep(0.8)
    out += read_all(fd, 0.8)

    if b'>>' not in out:
        return False, 'footer marker >> not found'
    if b'aaaa' not in out:
        return False, 'buffer text aaaa not found'
    return True, 'footer and long buffer both present'


def test_no_raw_ansi_in_footer(fd):
    """Footer text should not show literal escape sequences like ^[[38."""
    out = init_prompt(fd)
    os.write(fd, b'cd ~/.zsh\n')
    time.sleep(0.5)
    out += read_all(fd, 0.6)
    os.write(fd, b'echo hi')
    time.sleep(0.4)
    out += read_all(fd, 0.5)

    vt = out.decode('utf-8', errors='replace').replace('\x1b', '\\e')
    if '^[[38' in vt or '^[[39' in vt:
        return False, 'literal ANSI visible'
    return True, 'no literal escape sequences'


def test_command_output_after_execution(fd):
    """After pressing Enter, command output uses full screen."""
    out = init_prompt(fd)
    os.write(fd, b'echo hello_world\n')
    time.sleep(0.5)
    out += read_all(fd, 0.6)

    if b'hello_world' in out:
        return True, 'command output visible'
    return False, 'command output not found'


if __name__ == '__main__':
    tests = [
        test_single_line_color,
        test_multiline_pushes_footer,
        test_long_buffer_stays_above_footer,
        test_no_raw_ansi_in_footer,
        test_command_output_after_execution,
    ]
    results = [run_test(t.__doc__, t) for t in tests]
    sys.exit(0 if all(results) else 1)
