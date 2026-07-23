#!/usr/bin/env python3
"""
Test: No blank lines between consecutive prompts or between prompt and footer after Ctrl+C.

Screen after two Ctrl+C events should look like (with no blank lines):
    %
    %
    %
    >> ~/...
"""
import os, sys, pty, select, time, glob, shutil, re

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROBE_PATH = os.path.join(TEST_DIR, 'test_probe_ctrlc_bug.zsh')

LINES = 10


def spawn():
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
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


def wait_for_output(fd, min_bytes=10, max_wait=4.0):
    out = b''
    deadline = time.time() + max_wait
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.3)
        if r:
            try:
                chunk = os.read(fd, 8192)
                if not chunk:
                    break
                out += chunk
                if len(out) >= min_bytes:
                    break
            except OSError:
                break
    return out


class VirtualTerminal:
    """Simple 2D character buffer simulating a terminal screen."""
    def __init__(self, lines=10, cols=80):
        self.rows = lines
        self.cols = cols
        self.screen = [[' '] * cols for _ in range(lines)]
        self.cursor_row = 0
        self.cursor_col = 0

    def _handle_csi(self, text, i):
        """Handle a CSI escape sequence starting at text[i] (which is '[')."""
        i += 1  # skip '['
        params = ''
        while i < len(text):
            c = text[i]
            if '0' <= c <= '9' or c == ';' or c == '?':
                params += c
                i += 1
            else:
                break
        if i < len(text):
            cmd = text[i]
            if cmd == 'J':  # Erase in display
                if params == '2':
                    self.screen = [[' '] * self.cols for _ in range(self.rows)]
                elif params == '1':
                    for r in range(0, self.cursor_row + 1):
                        end_col = self.cursor_col if r == self.cursor_row else self.cols - 1
                        for c in range(0, end_col + 1):
                            self.screen[r][c] = ' '
                else:
                    for r in range(self.cursor_row, self.rows):
                        start_col = self.cursor_col if r == self.cursor_row else 0
                        for c in range(start_col, self.cols):
                            self.screen[r][c] = ' '
            elif cmd == 'K':  # Erase in line
                for c in range(self.cursor_col, self.cols):
                    self.screen[self.cursor_row][c] = ' '
            elif cmd == 'H':  # Cursor home
                if params == '':
                    self.cursor_row = 0; self.cursor_col = 0
                else:
                    parts = params.split(';')
                    row = int(parts[0]) if parts[0] else 0
                    col = int(parts[1]) if len(parts) > 1 and parts[1] else 0
                    self.cursor_row = max(0, row - 1)
                    self.cursor_col = max(0, col - 1)
            elif cmd == 'A':  # Cursor up
                n = 1
                if params and params.isdigit():
                    n = int(params)
                self.cursor_row = max(0, self.cursor_row - n)
            elif cmd == 'B':  # Cursor down
                n = 1
                if params and params.isdigit():
                    n = int(params)
                self.cursor_row = min(self.rows - 1, self.cursor_row + n)
            elif cmd == 'C':  # Cursor forward
                n = 1
                if params and params.isdigit():
                    n = int(params)
                self.cursor_col = min(self.cols - 1, self.cursor_col + n)
            elif cmd == 'D':  # Cursor back
                n = 1
                if params and params.isdigit():
                    n = int(params)
                self.cursor_col = max(0, self.cursor_col - n)
            i += 1
        return i

    def write(self, text):
        i = 0
        while i < len(text):
            c = text[i]
            if c == '\r':
                self.cursor_col = 0
            elif c == '\n':
                self.cursor_row += 1
                if self.cursor_row >= self.rows:
                    self._scroll()
                    self.cursor_row = self.rows - 1
            elif c == '\b' or c == '\x08':
                if self.cursor_col > 0:
                    self.cursor_col -= 1
            elif c == '\x1b':
                i += 1
                if i < len(text) and text[i] == '[':
                    i = self._handle_csi(text, i)
                    continue
                elif i < len(text) and text[i] == ']':
                    # OSC sequence, skip to BELL or ST
                    i += 1
                    while i < len(text):
                        if text[i] == '\x07': i += 1; break
                        if text[i] == '\x1b' and i+1 < len(text) and text[i+1] == '\\':
                            i += 2; break
                        i += 1
                    continue
                elif i < len(text):
                    i += 1
                    continue
            elif c == ' ' and self.cursor_col == self.cols:
                self.cursor_row += 1
                self.cursor_col = 0
                if self.cursor_row >= self.rows:
                    self._scroll()
                    self.cursor_row = self.rows - 1
            else:
                if 0 <= self.cursor_row < self.rows and 0 <= self.cursor_col < self.cols:
                    self.screen[self.cursor_row][self.cursor_col] = c
                self.cursor_col += 1
                if self.cursor_col >= self.cols:
                    self.cursor_col = 0
                    self.cursor_row += 1
                    if self.cursor_row >= self.rows:
                        self._scroll()
                        self.cursor_row = self.rows - 1
            i += 1

    def _scroll(self):
        self.screen.pop(0)
        self.screen.append([' '] * self.cols)

    def get_lines(self):
        return [''.join(row).rstrip() for row in self.screen]

    def count_matches(self, pattern):
        count = 0
        for row in self.screen:
            line = ''.join(row)
            if pattern in line:
                count += 1
        return count


def cleanup():
    for d in glob.glob('/tmp/zsh_probe_*'):
        shutil.rmtree(d, ignore_errors=True)


def run_test(name, fn):
    cleanup()
    pid, fd = spawn()
    time.sleep(1.0)
    ok, msg = False, 'exception'
    try:
        ok, msg = fn(fd)
    finally:
        try:
            os.write(fd, b'exit\n')
            time.sleep(0.3)
            os.close(fd)
            os.waitpid(pid, 0)
        except Exception:
            pass
        cleanup()
    status = 'PASS' if ok else 'FAIL'
    print(f'[{status}] {name}: {msg}')
    return ok


def test_no_blank_lines_between_prompts(fd):
    """After two Ctrl+C events, no blank lines between consecutive % prompts or between last % and footer."""
    init = wait_for_output(fd, min_bytes=30, max_wait=2.0)
    read_all(fd, 0.3)

    vt = VirtualTerminal(lines=LINES, cols=80)
    def feed(data):
        vt.write(data.decode('utf-8', errors='replace'))
    feed(init)

    # Run a command first to push the prompt down from row 0 (realistic usage)
    os.write(fd, b'echo A\n')
    time.sleep(0.5)
    run_out = read_all(fd, 0.3)
    feed(run_out)

    # Type a short command on the new prompt
    os.write(fd, b'echo hi')
    time.sleep(0.3)
    read_all(fd, 0.3)

    # Ctrl+C #1 (non-empty buffer)
    os.write(fd, b'\x03')
    time.sleep(0.4)
    c1 = read_all(fd, 0.3)
    feed(c1)

    # Ctrl+C #2 (empty buffer)
    os.write(fd, b'\x03')
    time.sleep(0.6)
    c2 = read_all(fd, 0.5)
    feed(c2)

    lines = vt.get_lines()
    after = vt.count_matches('>>')

    print("  Screen after two Ctrl+C:")
    for i, line in enumerate(lines):
        print(f"  [{i}] {line!r}")

    # Find non-empty lines starting from first '%' prompt (skip command output)
    prompt_indices = [i for i, l in enumerate(lines) if l.strip() and l.strip().startswith('%')]
    if not prompt_indices:
        return False, 'no % prompt found'
    first_prompt = prompt_indices[0]
    non_empty_indices = [i for i, l in enumerate(lines) if l.strip() and i >= first_prompt]

    # Between consecutive non-empty lines starting from first prompt, there must be no empty lines
    blank_gaps = []
    for idx in range(len(non_empty_indices) - 1):
        start = non_empty_indices[idx]
        end = non_empty_indices[idx + 1]
        blank_count = end - start - 1  # rows between them
        if blank_count > 0:
            blank_gaps.append((start, end, blank_count))

    if blank_gaps:
        for s, e, count in blank_gaps:
            print(f"  Gap: {count} blank line(s) between rows {s} and {e}")
        return False, f'{len(blank_gaps)} gap(s) found between non-empty lines (expected 0)'

    if after == 0:
        return False, 'no footer visible'
    if after > 1:
        return False, f'{after} stacked footers'

    return True, 'no blank gaps between prompts/footer'


if __name__ == '__main__':
    ok = run_test(test_no_blank_lines_between_prompts.__doc__,
                  test_no_blank_lines_between_prompts)
    sys.exit(0 if ok else 1)
