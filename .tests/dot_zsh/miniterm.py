#!/usr/bin/env python3
"""Minimal terminal screen model with SGR color tracking.

Tracks foreground/background colors per character so we can query
what color specific text appears in on the rendered screen.
"""
import re

class MiniTerm:
    DEFAULT_FG = -1  # -1 = default

    def __init__(self, cols=80, rows=24):
        self.cols = cols
        self.rows = rows
        self.cursor_row = 0
        self.cursor_col = 0
        self.saved_row = 0
        self.saved_col = 0
        # Current SGR state
        self.fg = -1  # current foreground color (-1 = default)
        self.bold = False
        # Each position: {'ch': char, 'fg': foreground color, 'bold': bool}
        self._grid = [[{'ch': ' ', 'fg': -1, 'bold': False} for _ in range(cols)] for _ in range(rows)]

    def _get_cell(self, r, c=None):
        if r < 0 or r >= self.rows:
            return None
        if c is None:
            c = self.cursor_col
        if c < 0 or c >= self.cols:
            return None
        return self._grid[r][c]

    def _put_char(self, ch):
        if ch == '\n':
            if self.cursor_row == self.rows - 1:
                self._grid.pop(0)
                self._grid.append([{'ch': ' ', 'fg': -1, 'bold': False} for _ in range(self.cols)])
            else:
                self.cursor_row += 1
            return
        if self.cursor_row >= self.rows:
            return
        cell = self._get_cell(self.cursor_row, self.cursor_col)
        if cell is not None:
            cell['ch'] = ch
            cell['fg'] = self.fg
            cell['bold'] = self.bold
        self.cursor_col += 1
        if self.cursor_col >= self.cols:
            self.cursor_col = 0
            if self.cursor_row < self.rows - 1:
                self.cursor_row += 1

    def _apply_sgr(self, params_str):
        """Apply SGR parameters (CSI Nm)."""
        if not params_str:
            params = [0]
        else:
            params = [int(p) if p else 0 for p in params_str.split(';')]
        i = 0
        while i < len(params):
            p = params[i]
            if p == 0:
                self.fg = -1
                self.bold = False
            elif p == 1:
                self.bold = True
            elif p == 22:
                self.bold = False
            elif p == 38:  # extended foreground
                i += 1
                if i < len(params) and params[i] == 5:
                    i += 1
                    if i < len(params):
                        self.fg = params[i]
                elif i < len(params) and params[i] == 2:
                    # rgb — skip next 3 params
                    i += 3
            elif p == 39:  # default foreground
                self.fg = -1
            elif 30 <= p <= 37:
                self.fg = p
            elif 90 <= p <= 97:
                self.fg = p
            i += 1

    def _clear_line(self, mode):
        """Clear parts of current line (CSI K)."""
        line = self._grid[self.cursor_row]
        default = {'ch': ' ', 'fg': -1, 'bold': False}
        if mode == 0:  # to end
            for c in range(self.cursor_col, self.cols):
                line[c] = dict(default)
        elif mode == 1:  # from start
            for c in range(0, self.cursor_col + 1):
                line[c] = dict(default)
        elif mode == 2:  # entire line
            for c in range(self.cols):
                line[c] = dict(default)

    def feed(self, data):
        if isinstance(data, bytes):
            data = data.decode('latin-1')
        i = 0
        while i < len(data):
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
                if i >= len(data):
                    break
                if data[i] == '[':
                    i += 1
                    if i < len(data) and data[i] == '?':
                        i += 1
                    params_str = ''
                    while i < len(data) and data[i] in '0123456789;':
                        params_str += data[i]
                        i += 1
                    if i >= len(data):
                        break
                    cmd = data[i]
                    i += 1
                    if cmd == 'A':
                        n = int(params_str) if params_str else 1
                        self.cursor_row = max(0, self.cursor_row - n)
                    elif cmd == 'B':
                        n = int(params_str) if params_str else 1
                        self.cursor_row = min(self.rows - 1, self.cursor_row + n)
                    elif cmd == 'C':
                        n = int(params_str) if params_str else 1
                        self.cursor_col = min(self.cols - 1, self.cursor_col + n)
                    elif cmd == 'D':
                        n = int(params_str) if params_str else 1
                        self.cursor_col = max(0, self.cursor_col - n)
                    elif cmd == 'G':
                        n = int(params_str) if params_str else 1
                        self.cursor_col = max(0, min(self.cols - 1, n - 1))
                    elif cmd == 'H':
                        parts = params_str.split(';')
                        r = int(parts[0]) - 1 if parts[0] else 0
                        c = int(parts[1]) - 1 if len(parts) > 1 and parts[1] else 0
                        self.cursor_row = max(0, min(self.rows - 1, r))
                        self.cursor_col = max(0, min(self.cols - 1, c))
                    elif cmd == 'K':
                        n = int(params_str) if params_str else 0
                        self._clear_line(n)
                    elif cmd == 'J':
                        self._grid = [[{'ch': ' ', 'fg': -1, 'bold': False} for _ in range(self.cols)] for _ in range(self.rows)]
                    elif cmd == 'm':
                        self._apply_sgr(params_str)
                    elif cmd == 's':
                        pass  # save cursor - handled by \033 s below
                    elif cmd == 'u':
                        pass
                    else:
                        pass
                elif data[i] == 's':
                    self.saved_row = self.cursor_row
                    self.saved_col = self.cursor_col
                    i += 1
                elif data[i] == 'u':
                    self.cursor_row = self.saved_row
                    self.cursor_col = self.saved_col
                    i += 1
                elif data[i] == ']':
                    i += 1
                    while i < len(data) and data[i] not in '\x07\x1b':
                        i += 1
                    if i < len(data):
                        if data[i] == '\x1b':
                            i += 1
                        elif data[i] == '\x07':
                            i += 1
                else:
                    i += 1
            elif ch == '\x07':
                i += 1
            else:
                self._put_char(ch)
                i += 1

    @property
    def display(self):
        return [''.join(cell['ch'] for cell in row).rstrip() for row in self._grid]

    def text_at(self, row, col_start, col_end=None):
        """Return text in a range on a given row."""
        if col_end is None:
            col_end = col_start + 1
        row_data = self._grid[row]
        chars = []
        for c in range(col_start, min(col_end, self.cols)):
            chars.append(row_data[c]['ch'])
        return ''.join(chars).rstrip()

    def fg_at(self, row, col):
        """Return foreground color at position, or -1 for default."""
        cell = self._grid[row][col]
        return cell['fg']

    def find_text(self, text):
        """Find (row, col_start) of first occurrence of text on screen."""
        for r in range(self.rows):
            line_chars = ''.join(cell['ch'] for cell in self._grid[r])
            c = line_chars.find(text)
            if c >= 0:
                return (r, c)
        return None

    def color_at_text(self, text):
        """Find text on screen and return its foreground color at start position.
        Returns (row, col, fg) or None if text not found."""
        pos = self.find_text(text)
        if pos is None:
            return None
        r, c = pos
        fg = self.fg_at(r, c)
        return (r, c, fg)

    def dump(self, with_color=True):
        for i in range(self.rows):
            line = self._grid[i]
            chars = ''.join(cell['ch'] for cell in line).rstrip()
            if chars:
                if with_color:
                    # Find colors in this line
                    fg_line = [cell['fg'] for cell in line if cell['ch'] != ' ']
                    fg_set = sorted(set(f for f in fg_line if f >= 0))
                    color_info = f'  fg={fg_set}' if fg_set else ''
                    print(f'  [{i:2d}] {chars[:80]}{color_info}')
                else:
                    print(f'  [{i:2d}] {chars[:80]}')

    @property
    def cursor_pos(self):
        return (self.cursor_row, self.cursor_col)


if __name__ == '__main__':
    t = MiniTerm(80, 24)
    t.feed(b'\x1b[1B\x1b[2K\x1b[G\x1b[1m\x1b[38;5;88mhello\x1b[0m')
    t.dump()
    print(t.color_at_text('hello'))
