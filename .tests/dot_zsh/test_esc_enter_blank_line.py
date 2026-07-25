#!/usr/bin/env python3
"""
RED test: Esc+Enter should NOT create a blank line.

Current behavior: ^[^M → self-insert-unmeta → inserts literal \r into buffer.
When Enter is pressed after, the \r causes display corruption including blank line.

Test: type "echo 123", Esc+Enter, Enter. Check raw output for blank lines
between the old prompt and the new prompt.
"""
import os, sys, pty, select, time, re

def read_until_stable(fd, timeout=0.3, max_total=5.0):
    out = b''
    start = time.time()
    while time.time() - start < max_total:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try:
            c = os.read(fd, 8192)
            if not c: break
            out += c
            start = time.time()
        except: break
    return out

def strip_ansi(data):
    """Remove ANSI escape sequences, keep text + newlines."""
    if isinstance(data, bytes):
        data = data.decode('latin-1')
    # Remove OSC sequences: ESC ] ... (BEL|ST)
    data = re.sub(r'\x1b\][^\x07\x1b]*[\x07\x1b\\]', '', data)
    # Remove CSI sequences: ESC [ params... letter
    # params = digits and semicolons and '?'
    data = re.sub(r'\x1b\[[\d;?]*[ABCDEFGHJKLMNPSTfghilmnrsu]', '', data)
    # Remove remaining ESC sequences (single char after ESC)
    data = re.sub(r'\x1b.', '', data)
    # Remove other control chars (keep \n, \r)
    data = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1a\x1c-\x1f]', '', data)
    # Replace BEL
    data = data.replace('\x07', '')
    return data

def run():
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
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)

    all_data = b''

    # Wait for initial prompt
    time.sleep(1.5)
    all_data += read_until_stable(fd, 0.5)

    # Type "echo 123"
    os.write(fd, b'echo 123')
    time.sleep(0.3)
    all_data += read_until_stable(fd, 0.2)

    # Esc + Enter (^[^M → self-insert-unmeta → inserts \r into buffer)
    os.write(fd, b'\033\r')
    time.sleep(1.0)
    all_data += read_until_stable(fd, 1.0)

    # Press Enter to submit the buffer
    os.write(fd, b'\n')
    time.sleep(1.5)
    all_data += read_until_stable(fd, 1.0)

    os.close(fd)
    os.waitpid(pid, 0)

    # Strip ANSI to get clean text
    text = strip_ansi(all_data)

    # Split on actual newline bytes only (NOT \r, which is used for column 0 positioning)
    lines = text.split('\n')

    print("=== Visible lines (ANSI-stripped) ===")
    for i, l in enumerate(lines):
        s = l.strip()
        if s:
            print(f'  [{i}] |{s}|')

    # Find lines containing "echo 123" and "%"
    echo_idx = None
    pct_indices = []
    for i, l in enumerate(lines):
        if 'echo 123' in l:
            echo_idx = i
        if l.strip().startswith('%'):
            pct_indices.append(i)

    print(f'\n  echo 123 at line {echo_idx}')
    print(f'  % at lines {pct_indices}')

    # Check: between "echo 123" line and the NEXT % prompt,
    # are there any blank lines?
    if echo_idx is not None:
        next_pct = None
        for i in pct_indices:
            if i > echo_idx:
                next_pct = i
                break

        if next_pct is not None:
            # Lines between echo_idx and next_pct (exclusive)
            between = lines[echo_idx + 1:next_pct]
            print(f'  Lines between echo 123 and next %: {len(between)}')
            for i, l in enumerate(between):
                print(f'    [{echo_idx+1+i}] |{l!r}|')

            # Count blank lines
            blank = sum(1 for l in between if not l.strip())
            if blank > 1:
                return False, f'{blank} blank lines between "echo 123" and next % prompt'
            elif blank == 1:
                # One blank line might be normal (newline after command)
                # Check if the non-blank lines include command output (like "123")
                has_output = any('123' in l for l in between)
                msg = f'1 blank line (output present={has_output}) between prompt lines'
                return False, msg

    return True, 'No excessive blank lines between prompts'

if __name__ == '__main__':
    ok, msg = False, 'exception'
    try: ok, msg = run()
    except Exception as e: msg = str(e)
    print(f'  {"PASS" if ok else "FAIL"}: {msg}')
    sys.exit(0 if ok else 1)
