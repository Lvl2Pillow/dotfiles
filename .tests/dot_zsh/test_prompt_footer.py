#!/usr/bin/env python3
"""Red/green tests for zsh prompt footer behavior.

Requires pyte. Install with:
  python3 -m venv .venv && .venv/bin/pip install pyte
  .venv/bin/python test_prompt_footer.py
"""
import os, sys, subprocess

# Try to use a local venv if present; otherwise assume system pyte.
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_SITE = os.path.join(TEST_DIR, '.venv', 'lib',
                         f'python{sys.version_info.major}.{sys.version_info.minor}',
                         'site-packages')
if os.path.isdir(VENV_SITE):
    sys.path.insert(0, VENV_SITE)

try:
    from pyte import Screen, Stream
except ImportError:
    print('pyte is required. Install with:')
    print(f'  cd {TEST_DIR}')
    print('  python3 -m venv .venv && .venv/bin/pip install pyte')
    print('  .venv/bin/python test_prompt_footer.py')
    sys.exit(1)

import pty, select, time, re

COLUMNS = 80
LINES = 24


def spawn_zsh():
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = str(COLUMNS)
        os.environ['LINES'] = str(LINES)
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


def render_screen(out_bytes):
    screen = Screen(LINES, COLUMNS)
    stream = Stream(screen)
    stream.feed(out_bytes.decode('utf-8', errors='replace'))
    return screen


def screen_lines(screen):
    return [''.join(screen.buffer[y][x].data for x in range(COLUMNS)).rstrip()
            for y in range(LINES)]


def find_footer_line(screen, text='~/.zsh'):
    lines = screen_lines(screen)
    for i in range(len(lines) - 1, -1, -1):
        if text in lines[i]:
            return i
    return -1


def find_buffer_bottom_line(screen, marker='aaaa'):
    lines = screen_lines(screen)
    for i in range(len(lines) - 1, -1, -1):
        if marker in lines[i]:
            return i
    return -1


def has_colored_footer_raw(out_bytes, text='~/.zsh'):
    idx = out_bytes.rfind(text.encode())
    if idx < 0:
        return False
    prefix = out_bytes[max(0, idx - 40):idx]
    return bool(re.search(rb'\x1b\[(38;5;\d+|1;\d+|0?\d+)m', prefix))


def run_test(name, fn):
    pid, fd = spawn_zsh()
    time.sleep(0.5)
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
    status = 'PASS' if ok else 'FAIL'
    print(f'[{status}] {name}: {msg}')
    return ok


def source_and_get_prompt(fd):
    os.write(fd, b'clear\n')
    time.sleep(0.2)
    out = read_all(fd, 0.4)
    os.write(fd, b'_PROMPT_FORCE_LOAD=1 source ~/.zsh/05_prompt.zsh\n')
    time.sleep(0.3)
    out += read_all(fd, 0.4)
    os.write(fd, b'cd ~/.zsh\n')
    time.sleep(0.3)
    out += read_all(fd, 0.4)
    return out


# ---------- TESTS ----------

def test_single_line_color(fd):
    """Footer below prompt is colored for short input."""
    out = source_and_get_prompt(fd)
    os.write(fd, b'echo hi')
    time.sleep(0.3)
    out += read_all(fd, 0.4)
    screen = render_screen(out)
    fl = find_footer_line(screen)
    if fl < 0:
        lines = screen_lines(screen)
        return False, f'no footer on screen; lines:\n' + '\n'.join(
            f'{i}: {l}' for i, l in enumerate(lines) if l)
    if not has_colored_footer_raw(out):
        return False, f'footer on line {fl} but not colored'
    return True, f'colored footer on line {fl}'


def test_multiline_pushes_footer(fd):
    """When buffer wraps, footer stays at bottom and buffer stays above it."""
    out = source_and_get_prompt(fd)
    os.write(fd, b'echo ')
    long = 'a' * 160
    os.write(fd, long.encode())
    time.sleep(0.8)
    out += read_all(fd, 0.8)
    screen = render_screen(out)
    fl = find_footer_line(screen)
    bl = find_buffer_bottom_line(screen)
    if fl < 0:
        lines = screen_lines(screen)
        return False, f'no footer on screen; lines:\n' + '\n'.join(
            f'{i}: {l}' for i, l in enumerate(lines) if l)
    if bl < 0:
        return False, 'no wrapped buffer on screen'
    if fl <= bl:
        lines = screen_lines(screen)
        return False, f'footer line {fl} not below buffer line {bl}; relevant lines:\n' + '\n'.join(
            f'{i}: {l}' for i, l in enumerate(lines) if i >= bl - 1)
    return True, f'footer on line {fl}, buffer ends on line {bl}'


def test_long_buffer_stays_above_footer(fd):
    """A long wrapping buffer does not overwrite the bottom footer."""
    out = source_and_get_prompt(fd)
    os.write(fd, b'echo ')
    long = 'a' * 400
    os.write(fd, long.encode())
    time.sleep(1.0)
    out += read_all(fd, 1.0)
    screen = render_screen(out)
    fl = find_footer_line(screen)
    if fl < 0:
        return False, 'no footer on screen'
    line = screen_lines(screen)[fl]
    if 'a' in line:
        return False, f'footer line {fl} contains buffer text: {line!r}'
    return True, f'footer line {fl} clean: {line!r}'


def test_no_raw_ansi_in_footer(fd):
    """Footer text should not show literal escape sequences like ^[[38."""
    out = source_and_get_prompt(fd)
    os.write(fd, b'echo hi')
    time.sleep(0.3)
    out += read_all(fd, 0.4)
    vt = out.decode('utf-8', errors='replace').replace('\x1b', '\\e')
    if '^[[38' in vt or '^[[39' in vt:
        return False, 'literal ANSI visible'
    return True, 'no literal escape sequences'


def test_command_output_after_execution(fd):
    """After pressing Enter, command output uses full screen (scroll region reset)."""
    out = source_and_get_prompt(fd)
    os.write(fd, b'echo hello_world\n')
    time.sleep(0.4)
    out += read_all(fd, 0.5)
    screen = render_screen(out)
    lines = screen_lines(screen)
    for line in lines:
        if 'hello_world' in line:
            return True, f'command output visible: {line!r}'
    return False, f'no hello_world in output; lines:\n' + '\n'.join(
        f'{i}: {l}' for i, l in enumerate(lines) if l)


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
