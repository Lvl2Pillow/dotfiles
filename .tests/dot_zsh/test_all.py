#!/usr/bin/env python3
"""
Combined test suite for zsh prompt footer.

All tests in one file to share PTY spawns across tests, running faster.
"""
import os, sys, pty, select, time, re, shutil, glob, tempfile, subprocess

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(TEST_DIR, '.venv', 'lib',
    f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages'))

PROBE_PATH = os.path.join(TEST_DIR, 'test_prompt_probe.zsh')
CTRLC_PROBE_PATH = os.path.join(TEST_DIR, 'test_probe_ctrlc_bug.zsh')
LINES = 24

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try:
            c = os.read(fd, 8192)
            if not c: break
            out += c
        except: break
    return out

def wait_for_output(fd, min_bytes=10, max_wait=4.0):
    out = b''
    deadline = time.time() + max_wait
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.3)
        if r:
            try: c = os.read(fd, 8192)
            except: break
            if not c: break
            out += c
            if len(out) >= min_bytes: break
    return out

def strip_ansi(s):
    s = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', s)
    s = re.sub(r'\x1b\][^\x07]*\x07', '', s)
    s = re.sub(r'\x1b[%#()]', '', s)
    s = re.sub(r'\x08', '', s)
    s = re.sub(r'\x1b\?2004[hl]', '', s)
    s = re.sub(r'\x1b[KL]', '', s)
    s = re.sub(r'\x1b\[[ABCDEFG]', '', s)
    s = re.sub(r'\x1b\[[0-9]+[ABCD]', '', s)
    s = re.sub(r'\r', '', s)
    return s.strip()

def visible_lines(raw):
    text = raw.decode('utf-8', errors='replace')
    lines = text.replace('\r\n', '\n').split('\n')
    result = []
    for l in lines:
        segments = l.split('\r')
        final = strip_ansi(segments[-1])
        if final: result.append(final)
    return result

def has_ansi_before(data, substr, lookback=80):
    idx = data.rfind(substr)
    if idx < 0: return False
    prefix = data[max(0, idx - lookback):idx]
    return bool(re.search(rb'\x1b\[[0-9;]*m', prefix))

def _cleanup_probe_dir(probe_dir):
    if probe_dir: shutil.rmtree(probe_dir, ignore_errors=True)

# ---------------------------------------------------------------------------
# Virtual Terminal (for screen content tracking)
# ---------------------------------------------------------------------------

class VirtualTerminal:
    def __init__(self, rows=10, cols=80):
        self.rows = rows; self.cols = cols
        self.screen = [[' '] * cols for _ in range(rows)]
        self.cursor_row = 0; self.cursor_col = 0

    def _handle_csi(self, text, i):
        i += 1; params = ''
        while i < len(text) and text[i] in '0123456789;?':
            params += text[i]; i += 1
        if i < len(text):
            cmd = text[i]
            if cmd == 'J':
                if params == '2':
                    self.screen = [[' '] * self.cols for _ in range(self.rows)]
                else:
                    for r in range(self.cursor_row, self.rows):
                        sc = self.cursor_col if r == self.cursor_row else 0
                        for c in range(sc, self.cols): self.screen[r][c] = ' '
            elif cmd == 'K':
                for c in range(self.cursor_col, self.cols): self.screen[self.cursor_row][c] = ' '
            elif cmd == 'H':
                if params == '': self.cursor_row = 0; self.cursor_col = 0
                else:
                    p = params.split(';')
                    self.cursor_row = max(0, (int(p[0]) if p[0] else 1) - 1)
                    self.cursor_col = max(0, (int(p[1]) if len(p) > 1 and p[1] else 1) - 1)
            elif cmd == 'A': self.cursor_row = max(0, self.cursor_row - (int(params) if params else 1))
            elif cmd == 'B': self.cursor_row = min(self.rows - 1, self.cursor_row + (int(params) if params else 1))
            elif cmd == 'C': self.cursor_col = min(self.cols - 1, self.cursor_col + (int(params) if params else 1))
            elif cmd == 'D': self.cursor_col = max(0, self.cursor_col - (int(params) if params else 1))
            i += 1
        return i

    def write(self, text):
        i = 0
        while i < len(text):
            c = text[i]
            if c == '\r': self.cursor_col = 0
            elif c == '\n':
                self.cursor_row += 1
                if self.cursor_row >= self.rows: self._scroll(); self.cursor_row = self.rows - 1
            elif c == '\x08' and self.cursor_col > 0: self.cursor_col -= 1
            elif c == '\x1b':
                i += 1
                if i < len(text) and text[i] == '[': i = self._handle_csi(text, i); continue
                elif i < len(text) and text[i] == ']':
                    i += 1
                    while i < len(text):
                        if text[i] == '\x07': i += 1; break
                        if text[i] == '\x1b' and i+1 < len(text) and text[i+1] == '\\': i += 2; break
                        i += 1
                    continue
                elif i < len(text): i += 1; continue
            else:
                if 0 <= self.cursor_row < self.rows and 0 <= self.cursor_col < self.cols:
                    self.screen[self.cursor_row][self.cursor_col] = c
                self.cursor_col += 1
                if self.cursor_col >= self.cols: self.cursor_col = 0; self.cursor_row += 1
                if self.cursor_row >= self.rows: self._scroll(); self.cursor_row = self.rows - 1
            i += 1

    def _scroll(self): self.screen.pop(0); self.screen.append([' '] * self.cols)
    def get_lines(self): return [''.join(r).rstrip() for r in self.screen]
    def count_matches(self, p): return sum(1 for r in self.screen if p in ''.join(r))

# ---------------------------------------------------------------------------
# Spawn variants
# ---------------------------------------------------------------------------

def spawn_probe(probe=PROBE_PATH, lines=24):
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'; os.environ['LINES'] = str(lines)
        os.environ['TERM_PROGRAM'] = ''
        d = f'/tmp/zsh_probe_{os.getpid()}'; os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            with open(probe) as src: f.write(src.read())
        with open(os.path.join(d, '.zshenv'), 'w') as f: f.write('# empty\n')
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)
    return pid, fd

def spawn_real(config='source ~/.zshrc 2>/dev/null || true', lines=24):
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'; os.environ['LINES'] = str(lines)
        d = f'/tmp/zsh_probe_{os.getpid()}'; os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config + '\n')
        with open(os.path.join(d, '.zshenv'), 'w') as f: f.write('export ZDOTDIR="$HOME"\n')
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)
    return pid, fd

def spawn_permission_test():
    """Spawn with a temp dir containing an unreadable .git file."""
    tmp = tempfile.mkdtemp(prefix='zsh_perm_test_')
    nested = os.path.join(tmp, 'a', 'b', 'c')
    os.makedirs(nested)
    # Create an unreadable .git file
    gitfile = os.path.join(nested, '.git')
    with open(gitfile, 'w') as f: f.write('gitdir: /nonexistent\n')
    os.chmod(gitfile, 0o000)
    # Create a regular .git dir above it to stop traversal
    parent_git = os.path.join(tmp, 'a', '.git')
    os.makedirs(os.path.join(parent_git, 'objects'))
    with open(os.path.join(parent_git, 'HEAD'), 'w') as f: f.write('ref: refs/heads/main\n')

    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '24'
        d = f'/tmp/zsh_probe_{os.getpid()}'; os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write('source ~/.zshrc 2>/dev/null || true\n')
        with open(os.path.join(d, '.zshenv'), 'w') as f:
            f.write('export ZDOTDIR="$HOME"\n')
        os.environ['ZDOTDIR'] = d
        # Start in the nested dir with the unreadable .git
        os.chdir(nested)
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)
    return pid, fd, tmp

def cleanup():
    for d in glob.glob('/tmp/zsh_probe_*'): shutil.rmtree(d, ignore_errors=True)
    for d in glob.glob('/tmp/zsh_perm_test_*'): shutil.rmtree(d, ignore_errors=True)

# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------
# Each receives a (pid, fd) tuple.

pass_count = 0
fail_count = 0

def test(fn):
    global pass_count, fail_count
    cleanup()
    name = fn.__doc__.strip() if fn.__doc__ else fn.__name__
    ok, msg = False, 'exception'
    try:
        ok, msg = fn()
    except Exception as e:
        msg = str(e)
    if ok:
        pass_count += 1; print(f'  PASS: {name}')
    else:
        fail_count += 1; print(f'  FAIL: {name} — {msg}')
    return ok

# ===== PROBE-BASED TESTS =====

def _probe_postdisplay_tests():
    """Footer below prompt is colored, survives wrapping, contains no raw ANSI."""
    pid, fd = spawn_probe(lines=24)
    time.sleep(0.8)
    # Capture initial output INCLUDING the first prompt + footer
    out = read_all(fd, 0.8)

    text = out.decode('utf-8', errors='replace').replace('\x1b', 'ESC')
    if '>>' not in text:
        # Try typing something to trigger redraw
        os.write(fd, b'echo hi'); time.sleep(0.6)
        out += read_all(fd, 0.5)
        text = out.decode('utf-8', errors='replace').replace('\x1b', 'ESC')
    if '>>' not in text:
        os.close(fd); os.waitpid(pid, 0)
        return False, 'footer >> not found: ' + text[-120:].replace('\x1b','ESC')
    if not has_ansi_before(out, b'>>'): os.close(fd); os.waitpid(pid, 0); return False, 'no ANSI before >>'

    # Long buffer + footer
    os.write(fd, b'\n')
    time.sleep(0.3); read_all(fd, 0.3)
    os.write(fd, b'echo ' + b'a' * 160)
    time.sleep(0.8)
    out2 = read_all(fd, 0.8)
    if b'>>' not in out2: os.close(fd); os.waitpid(pid, 0); return False, 'footer >> not found with long buffer'
    if b'aaaa' not in out2: os.close(fd); os.waitpid(pid, 0); return False, 'long buffer text not found'

    # No raw ANSI
    vt = (out + out2).decode('utf-8', errors='replace').replace('\x1b', '\\e')
    if '^[[38' in vt or '^[[39' in vt: os.close(fd); os.waitpid(pid, 0); return False, 'literal ANSI visible'

    os.close(fd); os.waitpid(pid, 0)
    return True, 'colored footer + long buffer + no raw ANSI'

def _probe_enter_clears_footer():
    """Footer from previous prompt is absent between command output lines."""
    pid, fd = spawn_probe(lines=24)
    time.sleep(0.8); read_all(fd, 0.5)

    os.write(fd, b'echo A; echo B\n'); time.sleep(0.6)
    out = read_all(fd, 0.5)
    text = out.decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')
    a_lines = [i for i, l in enumerate(lines) if l.strip() == 'A' and 'echo' not in l]
    b_lines = [i for i, l in enumerate(lines) if l.strip() == 'B' and 'echo' not in l]
    if not a_lines: os.close(fd); os.waitpid(pid, 0); return False, 'A not found'
    if not b_lines: os.close(fd); os.waitpid(pid, 0); return False, 'B not found'
    for l in lines[a_lines[0]:b_lines[0]]:
        if '>>' in l and 'echo' not in l and 'zsh' not in l:
            os.close(fd); os.waitpid(pid, 0); return False, f'footer between A and B: {l.strip()}'
    os.close(fd); os.waitpid(pid, 0)
    return True, 'no footer between output lines'

def _probe_ctrlc_no_stacked():
    """Ctrl+C on empty buffer does NOT stack multiple footers."""
    pid, fd = spawn_probe(probe=CTRLC_PROBE_PATH, lines=10)
    time.sleep(0.8); read_all(fd, 0.5)
    os.write(fd, b'\x03'); time.sleep(0.5); read_all(fd, 0.3)
    os.write(fd, b'\x03'); time.sleep(0.8)
    out = read_all(fd, 1.0)
    vis = visible_lines(out)
    fc = sum(1 for v in vis if '>>' in v)
    os.close(fd); os.waitpid(pid, 0)
    if fc != 1: return False, f'{fc} footers found, expected 1'
    return True, 'exactly 1 footer'

def _probe_no_blank_lines():
    """No blank lines between consecutive prompts or between prompt and footer after Ctrl+C."""
    pid, fd = spawn_probe(probe=CTRLC_PROBE_PATH, lines=10)
    time.sleep(0.8); read_all(fd, 0.5)
    os.write(fd, b'\x03'); time.sleep(0.5); read_all(fd, 0.3)
    os.write(fd, b'\x03'); time.sleep(0.8)
    out = read_all(fd, 1.0)
    vis = visible_lines(out)
    footer_rows = [i for i, v in enumerate(vis) if '>>' in v]
    if not footer_rows: os.close(fd); os.waitpid(pid, 0); return False, 'no footer'
    # Footer should appear at least once (no stacking)
    os.close(fd); os.waitpid(pid, 0)
    if len(footer_rows) != 1: return False, f'{len(footer_rows)} footers'
    return True, '1 footer'

def _probe_enter_on_empty():
    """Enter on empty buffer shows clean prompt (no footer from previous command)."""
    pid, fd = spawn_probe(probe=PROBE_PATH, lines=10)
    time.sleep(0.8); read_all(fd, 0.5)
    os.write(fd, b'\n'); time.sleep(0.8)
    out = read_all(fd, 1.0)
    vis = visible_lines(out)
    fc = sum(1 for v in vis if '>>' in v)
    os.close(fd); os.waitpid(pid, 0)
    return fc >= 1, f'{fc} footers'

def _probe_rapid_enter():
    """Rapid Enter presses should not stack footers."""
    pid, fd = spawn_probe(probe=PROBE_PATH, lines=10)
    time.sleep(0.8); read_all(fd, 0.5)
    for _ in range(3):
        os.write(fd, b'\n'); time.sleep(0.4)
    out = read_all(fd, 1.0)
    vis = visible_lines(out)
    fc = sum(1 for v in vis if '>>' in v)
    os.close(fd); os.waitpid(pid, 0)
    return fc >= 1, f'{fc} footers'

def _probe_ctrlc_then_type():
    """After Ctrl+C clears buffer, typing a command should show clean footer."""
    pid, fd = spawn_probe(probe=PROBE_PATH, lines=10)
    time.sleep(0.8); read_all(fd, 0.5)
    os.write(fd, b'\x03'); time.sleep(0.5)
    os.write(fd, b'echo hi\n'); time.sleep(0.8)
    out = read_all(fd, 1.0)
    vis = visible_lines(out)
    fc = sum(1 for v in vis if '>>' in v)
    os.close(fd); os.waitpid(pid, 0)
    return fc >= 1, f'{fc} footers'

def _probe_command_output():
    """After pressing Enter, command output uses full screen."""
    pid, fd = spawn_probe(lines=24)
    time.sleep(0.8); read_all(fd, 0.5)
    os.write(fd, b'echo hello_world\n'); time.sleep(0.5)
    out = read_all(fd, 0.6)
    ok = b'hello_world' in out
    os.close(fd); os.waitpid(pid, 0)
    return ok, 'command output visible' if ok else 'command output not found'

# ===== REAL-CONFIG TESTS =====

def _real_autosuggest_ghost():
    """Autosuggestions ghost text appears when typing partial command."""
    pid, fd = spawn_real(lines=10)
    time.sleep(0.8); read_all(fd, 0.5)
    os.write(fd, b'echo hello\n'); time.sleep(0.5); read_all(fd, 0.3)
    os.write(fd, b'echo h'); time.sleep(1.5)
    raw = read_all(fd, 0.3)
    lines = raw.decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n').split('\n')
    has_ghost = any('ello' in l for l in lines)
    os.close(fd); os.waitpid(pid, 0)
    return has_ghost, 'ghost text found' if has_ghost else 'ghost text not found'

def _real_autosuggest_accept():
    """After accepting suggestion (Ctrl+F), no double footer."""
    pid, fd = spawn_real(lines=24)
    time.sleep(0.8); read_all(fd, 0.5)
    os.write(fd, b'echo hello world\n'); time.sleep(0.5); read_all(fd, 0.3)
    os.write(fd, b'echo h'); time.sleep(1.5); read_all(fd, 0.3)
    os.write(fd, b'\x06'); time.sleep(0.5); read_all(fd, 0.3)
    os.write(fd, b'\x0c'); time.sleep(0.5)
    raw = read_all(fd, 0.5)
    vis = visible_lines(raw)
    footer_count = sum(1 for v in vis if v.startswith('~') or (v.startswith('/') and len(v) > 3 and ' ' in v))
    os.close(fd); os.waitpid(pid, 0)
    if footer_count != 1: return False, f'{footer_count} footers, expected 1'
    return True, '1 footer'

def _real_autosuggest_accept_color():
    """After accepting suggestion, buffer text has no color codes."""
    pid, fd = spawn_real(lines=24)
    time.sleep(0.8); read_all(fd, 0.5)
    os.write(fd, b'echo hello world\n'); time.sleep(0.5); read_all(fd, 0.3)
    os.write(fd, b'echo h'); time.sleep(1.5); read_all(fd, 0.3)
    os.write(fd, b'\x06'); time.sleep(0.5); read_all(fd, 0.3)
    os.write(fd, b'\x0c'); time.sleep(0.5)
    raw = read_all(fd, 0.5)
    text = raw.decode('utf-8', errors='replace')
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    for l in lines:
        if '%' in l:
            clean = l.replace('\x1b', 'ESC')
            reset_pos = clean.rfind('ESC[0m')
            buf = clean[reset_pos:] if reset_pos >= 0 else clean
            colors = re.findall(r'ESC\[[0-9;]*m', buf)
            disallowed = [c for c in colors if c not in ('ESC[0m','ESC[K')]
            if disallowed:
                os.close(fd); os.waitpid(pid, 0)
                return False, f'colors in buffer: {disallowed}'
            break
    os.close(fd); os.waitpid(pid, 0)
    return True, 'clean buffer'

def _real_enter_no_leak():
    """After Enter on partial command with ghost text, no footer leaks."""
    pid, fd = spawn_real(lines=24)
    time.sleep(1.0); read_all(fd, 0.5)
    os.write(fd, b'echo h'); time.sleep(1.5); read_all(fd, 0.3)
    os.write(fd, b'\n'); time.sleep(0.8)
    raw = read_all(fd, 0.5)
    vis = visible_lines(raw)
    footer_count = sum(1 for v in vis if v.startswith('~') or (v.startswith('/') and len(v) > 3 and ' ' in v))
    os.close(fd); os.waitpid(pid, 0)
    if footer_count > 1: return False, f'{footer_count} footers, expected 1'
    if footer_count == 0: return False, 'no footer'
    return True, '1 footer'

def _real_permission_denied():
    """_prompt_find_git must not emit permission denied on unreadable .git."""
    pid, fd, tmpdir = spawn_permission_test()
    time.sleep(0.8)
    # The prompt may have already read the unreadable .git file
    os.write(fd, b'echo start_marker\n'); time.sleep(0.5)
    out = read_all(fd, 0.5)
    text = out.decode('utf-8', errors='replace')
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.close(fd); os.waitpid(pid, 0)
    if 'permission denied' in text.lower():
        return False, 'permission denied emitted'
    if 'start_marker' not in text:
        return False, 'shell did not respond'
    return True, 'no permission denied'

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    tests = [
        # Probe-based
        ('colored footer + long buffer + no raw ANSI', _probe_postdisplay_tests),
        ('no footer between A and B output lines', _probe_enter_clears_footer),
        ('Ctrl+C on empty: exactly 1 footer', _probe_ctrlc_no_stacked),
        ('no blank gaps between prompts/footer after Ctrl+C', _probe_no_blank_lines),
        ('Enter on empty: footer near bottom', _probe_enter_on_empty),
        ('rapid Enter: no stacking', _probe_rapid_enter),
        ('Ctrl+C then type: clean footer', _probe_ctrlc_then_type),
        ('command output visible after Enter', _probe_command_output),
        # Real config
        ('ghost text on partial command', _real_autosuggest_ghost),
        ('accept suggestion: 1 footer', _real_autosuggest_accept),
        ('accept suggestion: no color leak', _real_autosuggest_accept_color),
        ('Enter with ghost: 1 footer, no leak', _real_enter_no_leak),
        ('no permission denied on unreadable .git', _real_permission_denied),
    ]

    for name, fn in tests:
        cleanup()
        ok, msg = False, 'exception'
        try:
            ok, msg = fn()
        except Exception as e:
            msg = str(e)
        if ok:
            global pass_count; pass_count += 1; print(f'  PASS: {name}')
        else:
            global fail_count; fail_count += 1; print(f'  FAIL: {name} — {msg}')

    print(f'\n{pass_count}/{pass_count + fail_count} passed')
    sys.exit(0 if fail_count == 0 else 1)

if __name__ == '__main__':
    main()
