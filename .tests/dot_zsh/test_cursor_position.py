#!/usr/bin/env python3
"""
RED test: cursor position after cd + Enter is right after '% ', not at end of footer.

Uses MiniTerm to track exact cursor column after typing a character.
After cd to chezmoi (which triggers async + TRAPUSR1), then pressing Enter,
the cursor should be at position 0 (right after '% '). Type 'x' and verify
it appears in the MiniTerm screen immediately after '% ' on the prompt row.
"""
import os, sys, pty, select, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.venv', 'lib',
    f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages'))
from miniterm import MiniTerm

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

def run():
    CHEZMOI = os.path.expanduser('~/.local/share/chezmoi')
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '24'
        d = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write('source ~/.zshrc 2>/dev/null || true\n')
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)

    time.sleep(1.0); read_all(fd, 0.3)

    # cd to chezmoi
    os.write(fd, f'cd {CHEZMOI}\n'.encode())
    time.sleep(3.0)  # wait for async + TRAPUSR1

    # Press Enter to get a fresh prompt
    os.write(fd, b'\n')
    time.sleep(1.5)

    # Drain output from Enter + new prompt rendering
    out_before = read_all(fd, 0.3)

    # Type 'x' — where does it appear on the screen?
    os.write(fd, b'x')
    time.sleep(0.5)

    out = out_before + read_all(fd, 0.3)

    os.write(fd, b'exit\n'); time.sleep(0.2)
    os.close(fd); os.waitpid(pid, 0)

    # Feed through MiniTerm to get visible screen with cursor tracking
    term = MiniTerm(80, 24)
    term.feed(out)

    # Find the row containing 'x'
    x_row = -1
    x_col = -1
    for i, line in enumerate(term.display):
        if 'x' in line:
            x_row = i
            x_col = line.find('x')
            print(f'  Found x at row {i}, col {x_col}: "{line[:60]}"')
            break

    # Also find row with '%' (prompt)
    pct_row = -1
    pct_col = -1
    for i, line in enumerate(term.display):
        if '%' in line:
            pct_row = i
            pct_col = line.find('%')
            print(f'  Found % at row {i}, col {pct_col}: "{line[:60]}"')
            break

    # Dump non-empty screen rows
    print('  --- screen ---')
    for i, line in enumerate(term.display):
        if line.strip():
            print(f'  [{i}] col {line.find("x") if "x" in line else "?":>3}: "{line[:80]}"')

    # Cursor should be ON THE PROMPT ROW, right after '% '
    if x_row < 0:
        return False, 'x not found on screen'

    if pct_row < 0:
        # Maybe '%' was cleared; check if x is at the top of the screen
        if x_col <= 3:
            return True, f'cursor at column {x_col} (likely right after % )'
        return False, f'x at column {x_col}, expected near column 0-3'

    if x_row == pct_row:
        # Same row: x should be right after '% '
        expected_col = pct_col + 2  # after '% '
        if abs(x_col - expected_col) <= 2:
            return True, f'cursor at col {x_col}, right after % (expected ~{expected_col})'
        else:
            return False, f'cursor at col {x_col} on prompt row, expected ~{expected_col}'
    else:
        return False, f'x on row {x_row}, % on row {pct_row} — cursor on wrong row'

if __name__ == '__main__':
    ok, msg = False, 'exception'
    try: ok, msg = run()
    except Exception as e: msg = str(e)
    print(f'  {"PASS" if ok else "FAIL"}: {msg}')
    sys.exit(0 if ok else 1)
