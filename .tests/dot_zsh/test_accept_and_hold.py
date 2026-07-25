#!/usr/bin/env python3
"""
RED test: accept-and-hold (Alt+A) inserts footer between prompt and output.

accept-and-hold is categorized by autosuggest as "modify" (catch-all).
Our $WIDGET check only matches *accept-line*, so _prompt_zle_append_footer
runs AFTER .accept-and-hold accepts the line. POSTDISPLAY footer is set,
then zle exits, trashzle renders the stale footer before command output.

Expected: % echo 88 → (newline) → 88 → (newline) → % echo 88 (held) → footer
Actual: % echo 88 → FOOTER → 88 → ...
"""
import os, sys, pty, select, time, re

def strip_ansi(data):
    if isinstance(data, bytes): data = data.decode('latin-1')
    data = re.sub(r'\x1b\][^\x07\x1b]*[\x07\x1b\\]', '', data)
    data = re.sub(r'\x1b\[[\d;?]*[ABCDEFGHJKLMNPSTfghilmnrsu]', '', data)
    data = re.sub(r'\x1b.', '', data)
    data = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1a\x1c-\x1f]', '', data)
    data = data.replace('\x07', '')
    return data

def find_footer_regions(raw_data, dir_name):
    """Find regions in raw data where footer is drawn.
    Footer is preceded by ESC[1B\r (cursor down + cr) and drawn character by character.
    Returns list of (start, end) byte ranges."""
    regions = []
    # Pattern: ESC[1B\r followed by ESC-styled text (the footer draw)
    idx = 0
    while True:
        marker = b'\x1b[1B\r'
        p = raw_data.find(marker, idx)
        if p < 0:
            break
        # This starts a footer region. Look for next ESC[A (cursor up) which ends it.
        end_marker = b'\x1b[A'
        end = raw_data.find(end_marker, p + len(marker))
        if end < 0:
            regions.append((p, len(raw_data)))
            break
        regions.append((p, end + len(end_marker)))
        idx = end + len(end_marker)
    return regions

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
    time.sleep(1.5)
    r, _, _ = select.select([fd], [], [], 0.5)
    if r: all_data += os.read(fd, 32768)

    # Type "echo 88"
    os.write(fd, b'echo 88')
    time.sleep(0.3)
    r, _, _ = select.select([fd], [], [], 0.2)
    if r: all_data += os.read(fd, 32768)

    # Alt+A (accept-and-hold)
    os.write(fd, b'\x1ba')
    time.sleep(1.5)
    r, _, _ = select.select([fd], [], [], 1.0)
    if r: all_data += os.read(fd, 32768)

    # Wait a bit more for command output
    time.sleep(0.5)
    r, _, _ = select.select([fd], [], [], 0.5)
    if r: all_data += os.read(fd, 32768)

    os.close(fd)
    os.waitpid(pid, 0)

    text = strip_ansi(all_data)
    
    # Find "echo 88" text echo (from typing)
    echo_pos = all_data.rfind(b'echo 88')
    if echo_pos < 0:
        echo_pos = all_data.rfind(b'88')  # fallback
    
    # Find "88" command output
    output_pos = all_data.rfind(b'\n88\r\n')
    if output_pos < 0:
        output_pos = all_data.rfind(b'88\r\n')
    
    print(f'  Echo "echo 88" at byte: {echo_pos}')
    print(f'  88 output at byte: {output_pos}')
    
    # Find all footer regions: ESC[1B\r NOT followed by another \r or \n
    # (must be an actual footer draw with text, not moveto in trashzle)
    idx = 0
    footers = []
    while True:
        p = all_data.find(b'\x1b[1B\r', idx)
        if p < 0: break
        # Check next char: if \r or \n, this is moveto, not footer draw
        next_byte = all_data[p + 5:p + 6] if p + 5 < len(all_data) else b''
        if next_byte not in (b'\r', b'\n'):
            end = all_data.find(b'\x1b[A', p + 5)
            if end < 0:
                end = len(all_data)
            else:
                end += 3  # include \x1b[A
            footers.append((p, end))
        idx = p + 5
    
    print(f'  Footer draws found: {len(footers)}')
    for i, (fs, fe) in enumerate(footers):
        context = all_data[fs:fe]
        stripped = strip_ansi(context)[:80]
        print(f'    [{i}] bytes {fs}-{fe}: |{stripped}|')
    
    # Bug check: is there a footer between echo and output?
    start = echo_pos if echo_pos >= 0 else 0
    end = output_pos if output_pos >= 0 else len(all_data)
    
    intrusive = []
    for fs, fe in footers:
        if start < fs < end:
            intrusive.append((fs, fe))
    
    if intrusive:
        for fs, fe in intrusive:
            context = all_data[fs:fe]
            stripped = strip_ansi(context)[:60]
            print(f'  INTRUSIVE footer at bytes {fs}-{fe}: |{stripped}|')
        return False, f'{len(intrusive)} footer(s) between echo and output'
    
    return True, 'No footer between prompt and command output'

if __name__ == '__main__':
    ok, msg = False, 'exception'
    try: ok, msg = run()
    except Exception as e: msg = str(e)
    print(f'  {"PASS" if ok else "FAIL"}: {msg}')
    sys.exit(0 if ok else 1)
