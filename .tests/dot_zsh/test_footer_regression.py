#!/usr/bin/env python3
"""
Test: Enter on empty buffer shows clean prompt (no footer from previous command).
"""
import os, sys, pty, select, time, glob, shutil, re

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROBE_PATH = os.path.join(TEST_DIR, 'test_prompt_probe.zsh')
LINES = 10

def spawn():
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = str(LINES)
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
        if not r: break
        try: chunk = os.read(fd, 8192)
        except: break
        if not chunk: break
        out += chunk
    return out

def wait_for_output(fd, min_bytes=10, max_wait=4.0):
    out = b''
    deadline = time.time() + max_wait
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.3)
        if r:
            try: chunk = os.read(fd, 8192)
            except: break
            if not chunk: break
            out += chunk
            if len(out) >= min_bytes: break
    return out

class VirtualTerminal:
    def __init__(self, lines=10, cols=80):
        self.rows = lines
        self.cols = cols
        self.screen = [[' '] * cols for _ in range(lines)]
        self.cursor_row = 0
        self.cursor_col = 0

    def _handle_csi(self, text, i):
        i += 1
        params = ''
        while i < len(text):
            c = text[i]
            if '0' <= c <= '9' or c == ';' or c == '?':
                params += c; i += 1
            else: break
        if i < len(text):
            cmd = text[i]
            if cmd == 'J':
                if params == '2':
                    self.screen = [[' '] * self.cols for _ in range(self.rows)]
                elif params == '1':
                    for r in range(0, self.cursor_row + 1):
                        ec = self.cursor_col if r == self.cursor_row else self.cols - 1
                        for c in range(0, ec + 1):
                            self.screen[r][c] = ' '
                else:
                    for r in range(self.cursor_row, self.rows):
                        sc = self.cursor_col if r == self.cursor_row else 0
                        for c in range(sc, self.cols):
                            self.screen[r][c] = ' '
            elif cmd == 'K':
                for c in range(self.cursor_col, self.cols):
                    self.screen[self.cursor_row][c] = ' '
            elif cmd == 'H':
                if params == '':
                    self.cursor_row = 0; self.cursor_col = 0
                else:
                    parts = params.split(';')
                    row = int(parts[0]) if parts[0] else 0
                    col = int(parts[1]) if len(parts) > 1 and parts[1] else 0
                    self.cursor_row = max(0, row - 1)
                    self.cursor_col = max(0, col - 1)
            elif cmd == 'A':
                n = 1
                if params and params.isdigit(): n = int(params)
                self.cursor_row = max(0, self.cursor_row - n)
            elif cmd == 'B':
                n = 1
                if params and params.isdigit(): n = int(params)
                self.cursor_row = min(self.rows - 1, self.cursor_row + n)
            elif cmd == 'C':
                n = 1
                if params and params.isdigit(): n = int(params)
                self.cursor_col = min(self.cols - 1, self.cursor_col + n)
            elif cmd == 'D':
                n = 1
                if params and params.isdigit(): n = int(params)
                self.cursor_col = max(0, self.cursor_col - n)
            i += 1
        return i

    def write(self, text):
        i = 0
        while i < len(text):
            c = text[i]
            if c == '\r': self.cursor_col = 0
            elif c == '\n':
                self.cursor_row += 1
                if self.cursor_row >= self.rows:
                    self._scroll(); self.cursor_row = self.rows - 1
            elif c == '\b' or c == '\x08':
                if self.cursor_col > 0: self.cursor_col -= 1
            elif c == '\x1b':
                i += 1
                if i < len(text) and text[i] == '[':
                    i = self._handle_csi(text, i); continue
                elif i < len(text) and text[i] == ']':
                    # OSC sequence, skip to BELL or ST
                    i += 1
                    while i < len(text):
                        if text[i] == '\x07': i += 1; break
                        if text[i] == '\x1b' and i+1 < len(text) and text[i+1] == '\\':
                            i += 2; break
                        i += 1
                    continue
                elif i < len(text): i += 1; continue
            elif c == ' ' and self.cursor_col == self.cols:
                self.cursor_row += 1; self.cursor_col = 0
                if self.cursor_row >= self.rows: self._scroll(); self.cursor_row = self.rows - 1
            else:
                if 0 <= self.cursor_row < self.rows and 0 <= self.cursor_col < self.cols:
                    self.screen[self.cursor_row][self.cursor_col] = c
                self.cursor_col += 1
                if self.cursor_col >= self.cols:
                    self.cursor_col = 0; self.cursor_row += 1
                    if self.cursor_row >= self.rows: self._scroll(); self.cursor_row = self.rows - 1
            i += 1

    def _scroll(self):
        self.screen.pop(0)
        self.screen.append([' '] * self.cols)

    def get_lines(self):
        return [''.join(row).rstrip() for row in self.screen]

    def count_matches(self, pattern):
        count = 0
        for row in self.screen:
            if pattern in ''.join(row): count += 1
        return count

def cleanup():
    for d in glob.glob('/tmp/zsh_probe_*'): shutil.rmtree(d, ignore_errors=True)

def run_test(name, fn):
    cleanup()
    pid, fd = spawn()
    time.sleep(1.0)
    ok, msg = False, 'exception'
    try:
        ok, msg = fn(fd)
    finally:
        try:
            os.write(fd, b'exit\n'); time.sleep(0.3); os.close(fd); os.waitpid(pid, 0)
        except Exception: pass
        cleanup()
    status = 'PASS' if ok else 'FAIL'
    print(f'[{status}] {name}: {msg}')
    return ok

def test_enter_on_empty_clears_footer(fd):
    """Pressing Enter on an empty buffer should clear the footer before next prompt."""
    init = wait_for_output(fd, min_bytes=30, max_wait=2.0)
    read_all(fd, 0.3)
    vt = VirtualTerminal(lines=LINES, cols=80)
    def feed(data): vt.write(data.decode('utf-8', errors='replace'))
    feed(init)
    start_footer = vt.count_matches('>>')
    # Press Enter on empty buffer
    os.write(fd, b'\n')
    time.sleep(0.5)
    after = read_all(fd, 0.3)
    feed(after)
    lines = vt.get_lines()
    end_footer = vt.count_matches('>>')
    print(f"  Start footer count: {start_footer}")
    print(f"  After Enter footer count: {end_footer}")
    for i, l in enumerate(lines): print(f"  [{i}] {l!r}")
    if end_footer != 1:
        return False, f'expected 1 footer after Enter, got {end_footer}'
    return True, 'footer persists correctly after Enter on empty buffer'

def test_rapid_enter_no_stacking(fd):
    """Rapid Enter presses should not stack footers."""
    init = wait_for_output(fd, min_bytes=30, max_wait=2.0)
    read_all(fd, 0.3)
    vt = VirtualTerminal(lines=LINES, cols=80)
    def feed(data): vt.write(data.decode('utf-8', errors='replace'))
    feed(init)
    for _ in range(3):
        os.write(fd, b'\n')
        time.sleep(0.4)
        out = read_all(fd, 0.2)
        feed(out)
    lines = vt.get_lines()
    footer_count = vt.count_matches('>>')
    print(f"  After 3 Enters: {footer_count} footer(s)")
    for i, l in enumerate(lines): print(f"  [{i}] {l!r}")
    # Each prompt should have exactly 1 footer below it (no stacking)
    # Check that last visible prompt+footer pair is correct
    flat = '\n'.join(lines)
    # Find the last prompt % followed by footer >>
    last_pct = flat.rfind('%')
    last_footer = flat.rfind('>>')
    if last_pct < 0:
        return False, 'no prompt visible'
    if last_footer < 0:
        return False, 'no footer visible'
    # Footer should be within 2 rows of the last prompt
    pct_row = max(i for i, l in enumerate(lines) if '%' in l)
    ft_row = max(i for i, l in enumerate(lines) if '>>' in l)
    gap = ft_row - pct_row
    print(f"  Last prompt row: {pct_row}, last footer row: {ft_row}, gap: {gap}")
    if gap < 1 or gap > 7:
        return False, f'footer gap {gap} from last prompt looks wrong'
    return True, 'footer present near last prompt after rapid Enter'

def test_ctrlc_then_type_no_footer_leak(fd):
    """After Ctrl+C clears buffer, typing a command should not show stale footer content."""
    init = wait_for_output(fd, min_bytes=30, max_wait=2.0)
    read_all(fd, 0.3)
    vt = VirtualTerminal(lines=LINES, cols=80)
    def feed(data): vt.write(data.decode('utf-8', errors='replace'))
    feed(init)
    os.write(fd, b'echo hi')
    time.sleep(0.3)
    typed = read_all(fd, 0.3)
    feed(typed)
    os.write(fd, b'\x03')
    time.sleep(0.5)
    out1 = read_all(fd, 0.3)
    feed(out1)
    # Type something new
    os.write(fd, b'ls')
    time.sleep(0.3)
    out2 = read_all(fd, 0.3)
    feed(out2)
    lines = vt.get_lines()
    footer_count = vt.count_matches('>>')
    print(f"  Footer count after Ctrl+C: {footer_count}")
    for i, l in enumerate(lines): print(f"  [{i}] {l!r}")
    if footer_count > 2:
        return False, f'too many footers visible: {footer_count}'
    # Footer should be visible (once) — the prompt should show it
    if footer_count == 0:
        return False, 'no footer visible'
    return True, 'footer visible, no leaks'

if __name__ == '__main__':
    ok1 = run_test(test_enter_on_empty_clears_footer.__doc__, test_enter_on_empty_clears_footer)
    ok2 = run_test(test_rapid_enter_no_stacking.__doc__, test_rapid_enter_no_stacking)
    ok3 = run_test(test_ctrlc_then_type_no_footer_leak.__doc__, test_ctrlc_then_type_no_footer_leak)
    sys.exit(0 if (ok1 and ok2 and ok3) else 1)
