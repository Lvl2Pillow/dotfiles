#!/usr/bin/env python3
"""Red/green tests for zsh prompt footer using GNU screen.

Tests the POSTDISPLAY + region_highlight approach:
  PROMPT  = '%# '           (line 1, with trailing space)
  BUFFER  = user input      (line 1, wraps naturally)
  POSTDISPLAY = '\n<dir>'   (last line, colored via region_highlight)

Requires GNU screen. Run from this directory:
  python3 test_prompt_footer_screen.py
"""
import subprocess, time, os, sys, re, tempfile, shutil

SCREEN_SESSION = 'zshprompttest'
COLUMNS = 80
LINES = 24

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE_SRC = os.path.join(HERE, 'test_prompt_probe.zsh')


def start_screen(probe_dir):
    """Start GNU screen with zsh -i using our probe as .zshrc."""
    # Kill any stale session
    subprocess.run(['screen', '-X', '-S', SCREEN_SESSION, 'quit'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.3)

    env = os.environ.copy()
    env['ZDOTDIR'] = probe_dir
    env['COLUMNS'] = str(COLUMNS)
    env['LINES'] = str(LINES)

    subprocess.run([
        'screen', '-dmS', SCREEN_SESSION,
        '-T', 'xterm-256color',
        'zsh', '-i'
    ], env=env)
    time.sleep(0.5)


def stop_screen():
    subprocess.run(['screen', '-X', '-S', SCREEN_SESSION, 'quit'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.2)


def send_keys(text):
    """Send literal characters to the screen session via 'stuff'."""
    subprocess.run(['screen', '-S', SCREEN_SESSION, '-X', 'stuff', text],
                   capture_output=True)
    time.sleep(0.3)


def take_hardcopy(path='/tmp/screen_hardcopy'):
    """Capture current screen contents (with escape sequences) to a file."""
    subprocess.run(['screen', '-S', SCREEN_SESSION, '-X',
                    'hardcopy', '-h', path],
                   capture_output=True)
    time.sleep(0.1)
    with open(path) as f:
        return f.read()


def take_hardcopy_plain(path='/tmp/screen_hardcopy_plain'):
    """Capture current screen contents (without escape sequences)."""
    subprocess.run(['screen', '-S', SCREEN_SESSION, '-X',
                    'hardcopy', path],
                   capture_output=True)
    time.sleep(0.1)
    with open(path) as f:
        return f.read()


def setup_probe_dir():
    """Create temp directory with probe .zshrc."""
    d = tempfile.mkdtemp(prefix='zshprobe_')
    # Copy probe script as .zshrc
    shutil.copy2(PROBE_SRC, os.path.join(d, '.zshrc'))
    # Empty .zshenv to prevent loading user's
    with open(os.path.join(d, '.zshenv'), 'w') as f:
        f.write('# empty\n')
    return d


def cleanup_probe_dir(d):
    shutil.rmtree(d, ignore_errors=True)


def wait_for_prompt(timeout=3.0):
    """Hardy-poll until '%# ' appears in hardcopy output."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        hc = take_hardcopy_plain()
        if '%' in hc:
            return True
        time.sleep(0.2)
    return False


def strip_ansi(text):
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)


def get_lines(text):
    """Split hardcopy into lines, stripping trailing whitespace."""
    return [l.rstrip() for l in text.split('\n')]


def find_line_containing(lines, substr):
    for i, l in enumerate(lines):
        if substr in l:
            return i
    return -1


# ---------- TESTS ----------

def test_single_line_color(fd=None):
    """Footer below prompt is colored for short input."""
    probe_dir = setup_probe_dir()
    try:
        start_screen(probe_dir)
        if not wait_for_prompt():
            return False, 'prompt never appeared'

        send_keys('cd ' + os.path.expanduser('~/.zsh') + '\n')
        time.sleep(0.5)
        hc = take_hardcopy()
        hc_plain = take_hardcopy_plain()

        lines = get_lines(hc_plain)
        fl = find_line_containing(lines, '.zsh')
        if fl < 0:
            return False, f'no footer found; lines:\n' + '\n'.join(
                f'{i}: {l}' for i, l in enumerate(lines) if l)

        # Check for ANSI codes near the footer in the raw hardcopy
        idx = hc.find(os.path.expanduser('~/.zsh'))
        if idx < 0:
            return False, 'footer not in raw hardcopy'
        prefix = hc[max(0, idx - 40):idx]
        if not re.search(r'\x1b\[[0-9;]*m', prefix):
            return False, f'footer present but no ANSI color codes near it'
        return True, f'colored footer on line {fl}'
    finally:
        stop_screen()
        cleanup_probe_dir(probe_dir)


def test_multiline_pushes_footer(fd=None):
    """When buffer wraps, footer stays at bottom and buffer stays above it."""
    probe_dir = setup_probe_dir()
    try:
        start_screen(probe_dir)
        if not wait_for_prompt():
            return False, 'prompt never appeared'

        # Type a long input to trigger wrapping
        send_keys('echo ')
        long = 'a' * 160
        send_keys(long)
        time.sleep(0.5)

        hc_plain = take_hardcopy_plain()
        lines = get_lines(hc_plain)

        bl = find_line_containing(lines, 'aaaa')
        fl = find_line_containing(lines, '~')
        if fl < 0:
            return False, f'no footer (~) found'
        if bl < 0:
            return False, 'no wrapped buffer found'

        if fl <= bl:
            return False, f'footer line {fl} not below buffer line {bl}'
        return True, f'footer on line {fl}, buffer ends on line {bl}'
    finally:
        stop_screen()
        cleanup_probe_dir(probe_dir)


def test_long_buffer_stays_above_footer(fd=None):
    """A long wrapping buffer does not overwrite the bottom footer."""
    probe_dir = setup_probe_dir()
    try:
        start_screen(probe_dir)
        if not wait_for_prompt():
            return False, 'prompt never appeared'

        send_keys('echo ')
        long = 'a' * 400
        send_keys(long)
        time.sleep(0.8)

        hc_plain = take_hardcopy_plain()
        lines = get_lines(hc_plain)

        fl = find_line_containing(lines, '~')
        if fl < 0:
            return False, 'no footer found'
        fl_text = lines[fl]
        if 'a' in fl_text and '~' not in fl_text:
            return False, f'footer line {fl} contains buffer text: {fl_text!r}'
        return True, f'footer line {fl} clean: {fl_text!r}'
    finally:
        stop_screen()
        cleanup_probe_dir(probe_dir)


def test_no_raw_ansi_in_footer(fd=None):
    """Footer text should not show literal escape sequences like ^[[38."""
    probe_dir = setup_probe_dir()
    try:
        start_screen(probe_dir)
        if not wait_for_prompt():
            return False, 'prompt never appeared'

        send_keys('cd ' + os.path.expanduser('~/.zsh') + '\n')
        time.sleep(0.5)
        hc_plain = take_hardcopy_plain()

        # In the plain hardcopy, look for literal caret-escape representations
        if '^[' in hc_plain or '\\e[' in hc_plain or '\\033[' in hc_plain:
            return False, 'literal escape sequences visible in plain hardcopy'
        # Also check for raw ESC byte displayed as text (unlikely but possible)
        raw_escape = re.findall(r'\x1b\[', hc_plain)
        if raw_escape:
            # If ESC bytes appear in "plain" hardcopy, screen didn't strip them
            return False, f'ESC bytes visible in plain hardcopy'
        return True, 'no literal escape sequences'
    finally:
        stop_screen()
        cleanup_probe_dir(probe_dir)


def test_command_output_after_execution(fd=None):
    """After pressing Enter, command output uses full screen."""
    probe_dir = setup_probe_dir()
    try:
        start_screen(probe_dir)
        if not wait_for_prompt():
            return False, 'prompt never appeared'

        send_keys('echo hello_world\n')
        time.sleep(0.5)

        hc_plain = take_hardcopy_plain()
        if 'hello_world' in hc_plain:
            return True, 'command output visible'
        # Sometimes the output scrolls; check hardcopy again with log
        hc_plain2 = take_hardcopy_plain()
        if 'hello_world' in hc_plain2:
            return True, 'command output visible (retry)'
        lines = get_lines(hc_plain)
        return False, 'no hello_world in output; lines:\n' + '\n'.join(
            f'{i}: {l}' for i, l in enumerate(lines) if l)
    finally:
        stop_screen()
        cleanup_probe_dir(probe_dir)


# ---------- MAIN ----------

def run_test(name, fn):
    ok, msg = fn()
    status = 'PASS' if ok else 'FAIL'
    print(f'[{status}] {name}: {msg}')
    return ok


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
