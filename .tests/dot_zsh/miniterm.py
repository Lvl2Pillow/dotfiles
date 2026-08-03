#!/usr/bin/env python3
"""Minimal terminal screen model with SGR color tracking.

Tracks foreground/background colors per character so we can query
what color specific text appears in on the rendered screen.
"""
import re

class MiniTerm:
    DEFAULT_FG = -1

    def __init__(self, cols=80, rows=24, debug=False):
        self.cols = cols
        self.rows = rows
        self.debug = debug
        self.cursor_row = 0
        self.cursor_col = 0
        self._saved_row = 0
        self._saved_col = 0
        # current SGR state
        self.fg = -1
        self.bold = False
        # cell: {'ch': char, 'fg': int, 'bold': bool}
        _empty = {'ch': ' ', 'fg': -1, 'bold': False}
        self._grid = [[dict(_empty) for _ in range(cols)] for _ in range(rows)]
        self._empty = _empty
        self._display_cache = None

    def _cell(self, r, c=None):
        if c is None:
            c = self.cursor_col
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            return None
        return self._grid[r][c]

    def _invalidate_cache(self):
        self._display_cache = None

    def _scroll_up(self):
        self._grid.pop(0)
        self._grid.append([dict(self._empty) for _ in range(self.cols)])
        if self.cursor_row > 0:
            self.cursor_row -= 1

    def _put_char(self, ch):
        if ch == '\n':
            if self.cursor_row == self.rows - 1:
                self._scroll_up()
            else:
                self.cursor_row += 1
            self._invalidate_cache()
            return
        if self.cursor_row >= self.rows:
            return
        cell = self._cell(self.cursor_row, self.cursor_col)
        if cell is not None:
            cell['ch'] = ch
            cell['fg'] = self.fg
            cell['bold'] = self.bold
        self.cursor_col += 1
        if self.cursor_col >= self.cols:
            self.cursor_col = 0
            if self.cursor_row < self.rows - 1:
                self.cursor_row += 1
            else:
                self._scroll_up()
        self._invalidate_cache()

    def _apply_sgr(self, params_str):
        if not params_str:
            params = [0]
        else:
            params = [int(p) if p else 0 for p in params_str.split(';')]
        i = 0
        while i < len(params):
            p = params[i]
            if p == 0:
                self.fg = -1; self.bold = False
            elif p == 1:
                self.bold = True
            elif p == 22:
                self.bold = False
            elif p == 38:
                i += 1
                if i < len(params) and params[i] == 5:
                    i += 1
                    if i < len(params):
                        self.fg = params[i]
                elif i < len(params) and params[i] == 2:
                    i += 3  # r;g;b
            elif p == 39:
                self.fg = -1
            elif 30 <= p <= 37:
                self.fg = p
            elif 90 <= p <= 97:
                self.fg = p
            i += 1

    def _clear_line(self, mode):
        line = self._grid[self.cursor_row]
        if mode == 0:
            for c in range(self.cursor_col, self.cols):
                line[c] = dict(self._empty)
        elif mode == 1:
            for c in range(0, self.cursor_col + 1):
                line[c] = dict(self._empty)
        elif mode == 2:
            for c in range(self.cols):
                line[c] = dict(self._empty)
        self._invalidate_cache()

    def _unknown_seq(self, label, raw):
        if self.debug:
            import sys
            print(f'  [miniterm] unknown: {label} raw={raw!r}', file=sys.stderr)

    def feed(self, data):
        if isinstance(data, bytes):
            data = data.decode('latin-1')
        i = 0
        n = len(data)
        while i < n:
            ch = data[i]
            if ch == '\r':
                self.cursor_col = 0
                i += 1
            elif ch == '\n':
                self._put_char('\n')
                i += 1
            elif ch == '\x08':
                self.cursor_col = max(0, self.cursor_col - 1)
                i += 1
            elif ch == '\x1b':
                i += 1
                if i >= n:
                    break
                nxt = data[i]
                # DECSC / DECRC (ESC 7 / ESC 8)
                if nxt == '7':
                    self._saved_row = self.cursor_row
                    self._saved_col = self.cursor_col
                    i += 1
                elif nxt == '8':
                    self.cursor_row = self._saved_row
                    self.cursor_col = self._saved_col
                    i += 1
                # SCP / RCP (ESC s / ESC u) — also supported
                elif nxt == 's':
                    self._saved_row = self.cursor_row
                    self._saved_col = self.cursor_col
                    i += 1
                elif nxt == 'u':
                    self.cursor_row = self._saved_row
                    self.cursor_col = self._saved_col
                    i += 1
                # CSI: ESC [
                elif nxt == '[':
                    i += 1
                    if i >= n:
                        break
                    private = False
                    if data[i] == '?':
                        private = True
                        i += 1
                    params_str = ''
                    while i < n and data[i] in '0123456789;':
                        params_str += data[i]
                        i += 1
                    if i >= n:
                        break
                    cmd = data[i]
                    i += 1
                    if cmd == 'A':
                        n2 = int(params_str) if params_str else 1
                        self.cursor_row = max(0, self.cursor_row - n2)
                    elif cmd == 'B':
                        n2 = int(params_str) if params_str else 1
                        self.cursor_row = min(self.rows - 1, self.cursor_row + n2)
                    elif cmd == 'C':
                        n2 = int(params_str) if params_str else 1
                        self.cursor_col = min(self.cols - 1, self.cursor_col + n2)
                    elif cmd == 'D':
                        n2 = int(params_str) if params_str else 1
                        self.cursor_col = max(0, self.cursor_col - n2)
                    elif cmd == 'G':
                        n2 = int(params_str) if params_str else 1
                        self.cursor_col = max(0, min(self.cols - 1, n2 - 1))
                    elif cmd == 'H':
                        parts = params_str.split(';')
                        r = int(parts[0]) - 1 if parts[0] else 0
                        c = int(parts[1]) - 1 if len(parts) > 1 and parts[1] else 0
                        self.cursor_row = max(0, min(self.rows - 1, r))
                        self.cursor_col = max(0, min(self.cols - 1, c))
                    elif cmd == 'K':
                        n2 = int(params_str) if params_str else 0
                        self._clear_line(n2)
                    elif cmd == 'J':
                        # ED: clear display. Mode 0 (default) = cursor to end
                        # of screen, 1 = start to cursor, 2 = whole screen.
                        # (zle emits plain ESC[J for clear-below; treating it
                        # as a full wipe loses rows above the cursor.)
                        mode = int(params_str) if params_str else 0
                        if mode == 2:
                            self._grid = [[dict(self._empty) for _ in range(self.cols)] for _ in range(self.rows)]
                        else:
                            for r in range(self.rows):
                                if mode == 0:
                                    if r < self.cursor_row:
                                        continue
                                    c0 = self.cursor_col if r == self.cursor_row else 0
                                else:  # mode == 1
                                    if r > self.cursor_row:
                                        break
                                    c0 = 0
                                    if r == self.cursor_row:
                                        for c in range(c0, self.cursor_col + 1):
                                            self._grid[r][c] = dict(self._empty)
                                        continue
                                for c in range(c0, self.cols):
                                    self._grid[r][c] = dict(self._empty)
                        self._invalidate_cache()
                    elif cmd == 'm':
                        self._apply_sgr(params_str)
                    elif cmd == 's':  # CSI s = SCP
                        self._saved_row = self.cursor_row
                        self._saved_col = self.cursor_col
                    elif cmd == 'u':  # CSI u = RCP
                        self.cursor_row = self._saved_row
                        self.cursor_col = self._saved_col
                    elif cmd == 'h' and private:
                        pass  # DEC private mode set (cursor visible, etc.)
                    elif cmd == 'l' and private:
                        pass  # DEC private mode reset (cursor hidden, etc.)
                    else:
                        self._unknown_seq(f'CSI {params_str}{cmd}', data[i-len(params_str)-2:i])
                # OSC: ESC ]
                elif nxt == ']':
                    i += 1
                    while i < n and data[i] not in '\x07\x1b':
                        i += 1
                    if i < n:
                        if data[i] == '\x1b':
                            i += 2
                        elif data[i] == '\x07':
                            i += 1
                else:
                    self._unknown_seq(f'ESC {ord(nxt):02x} ({nxt!r})', data[i-1:i+1])
                    i += 1
            elif ch == '\x07':
                i += 1
            else:
                self._put_char(ch)
                i += 1

    @property
    def display(self):
        if self._display_cache is None:
            self._display_cache = [''.join(cell['ch'] for cell in row) for row in self._grid]
        return self._display_cache

    def text_at(self, row, col_start, col_end=None):
        if col_end is None:
            col_end = col_start + 1
        row_data = self._grid[row]
        return ''.join(row_data[c]['ch'] for c in range(col_start, min(col_end, self.cols))).rstrip()

    def fg_at(self, row, col):
        cell = self._grid[row][col]
        return cell['fg']

    def find_text(self, text):
        for r in range(self.rows):
            line_chars = ''.join(self._grid[r][c]['ch'] for c in range(self.cols))
            c = line_chars.find(text)
            if c >= 0:
                return (r, c)
        return None

    def color_at_text(self, text):
        pos = self.find_text(text)
        if pos is None:
            return None
        r, c = pos
        return (r, c, self.fg_at(r, c))

    def dump(self, with_color=True):
        for i in range(self.rows):
            line = self.display[i].rstrip()
            if not line:
                continue
            if with_color:
                fg_vals = [self._grid[i][c]['fg'] for c in range(len(line))]
                fg_set = sorted(set(f for f in fg_vals if f >= 0))
                color_info = f'  fg={fg_set}' if fg_set else ''
                print(f'  [{i:2d}] {line[:80]}{color_info}')
            else:
                print(f'  [{i:2d}] {line[:80]}')

    @property
    def cursor_pos(self):
        return (self.cursor_row, self.cursor_col)


if __name__ == '__main__':
    t = MiniTerm(80, 24, debug=True)
    t.feed(b'\x1b[1B\x1b[2K\x1b[G\x1b[1m\x1b[38;5;88mhello\x1b[0m')
    t.dump()
    print(t.color_at_text('hello'))
