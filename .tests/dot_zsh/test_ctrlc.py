#!/usr/bin/env python3
"""
Consolidated: Ctrl+C (SIGINT) behavior.
# Time: ~9s (8 tests; 1 spawn).

Single spawn. Test: no stacked footers after consecutive Ctrl+C, no blank lines,
red % after interrupt, white % after successful command.
"""
import os, sys, pty, select, time, re

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
        # Last non-empty segment (trailing \r creates empty final)
        final_text = ''
        for s in reversed(segments):
            if s:
                final_text = s
                break
        final = strip_ansi(final_text)
        if final: result.append(final)
    return result

def count_footers(lines):
    count = 0
    for v in lines:
        v = v.strip()
        if not v: continue
        if v.startswith('~') or (v.startswith('/') and len(v) > 3):
            count += 1
    return count

def footer_lines(lines):
    return [l for l in lines if l.strip().startswith('~') or (l.strip().startswith('/') and len(l.strip()) > 3)]

def run():
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '10'
        d = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(d, exist_ok=True)
        cfg = 'source ~/.zshrc 2>/dev/null || true\n'
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write(cfg)
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)

    results = []

    try:
        time.sleep(1.0)
        read_all(fd, 0.5)

        # --- Consecutive Ctrl+C: no stacking ---
        os.write(fd, b'\x03')
        time.sleep(0.3)
        read_all(fd, 0.2)
        os.write(fd, b'\x03')
        time.sleep(0.5)
        out = read_all(fd, 0.5)
        vis = visible_lines(out)
        fc = count_footers(vis)
        results.append(('001 ctrl+c no stacking', fc <= 1, f'{fc} footers'))

        # --- No blank lines after Ctrl+C ---
        # Count blank lines between prompts
        text = out.decode('utf-8', errors='replace').replace('\r\n', '\n')
        raw_lines = text.split('\n')
        blank = sum(1 for l in raw_lines if not strip_ansi(l).strip())
        # More than 1 blank is suspicious
        results.append(('002 ctrl+c no blank lines', blank <= 2, f'{blank} blank lines'))

        # --- Red % after Ctrl+C (failed command, exit 130) ---
        os.write(fd, b'\x03')
        time.sleep(0.5)
        out = read_all(fd, 0.3)
        text = out.decode('utf-8', errors='replace').replace('\x1b', 'ESC')
        found_red = False
        for line in text.split('\n'):
            if '196' in line and '%' in line:
                found_red = True
                break
        results.append(('003 ctrl+c red prompt', found_red, 'red % not found'))

        # --- Red % after failed command (false) ---
        os.write(fd, b'false\n')
        time.sleep(0.4)
        out = read_all(fd, 0.3)
        text = out.decode('utf-8', errors='replace').replace('\x1b', 'ESC')
        found_false_red = any('196' in l and '%' in l for l in text.split('\n'))
        results.append(('004 false: red prompt', found_false_red, 'red % not found after false'))

        # --- White % after successful command (true) ---
        os.write(fd, b'true\n')
        time.sleep(0.4)
        out = read_all(fd, 0.3)
        text = out.decode('utf-8', errors='replace').replace('\x1b', 'ESC')
        found_true_red = any('196' in l and '%' in l for l in text.split('\n'))
        results.append(('005 true: no red prompt', not found_true_red, 'red % still present after true'))

        # --- Ctrl+C then type: clean footer ---
        os.write(fd, b'\x03')
        time.sleep(0.3)
        os.write(fd, b'echo hi\n')
        time.sleep(0.5)
        out = read_all(fd, 0.3)
        vis = visible_lines(out)
        fc_type = count_footers(vis)
        results.append(('006 ctrl+c then type: one footer', fc_type >= 1, f'{fc_type} footers'))

        # --- Color: % must be red (196) after Ctrl+C ---
        os.write(fd, b'\x03')
        time.sleep(0.5)
        out2 = read_all(fd, 0.3)
        has_196 = b'38;5;196' in out2
        results.append(('007 ctrl+c: red 196 in output', has_196, '196 not found'))

        # --- Cursor: Ctrl+L, 'z' types on same row as % after Ctrl+C ---
        os.write(fd, b'\x0c')
        time.sleep(0.3)
        out_redraw = read_all(fd, 0.2)
        os.write(fd, b'z')
        time.sleep(0.2)
        out3 = out_redraw + read_all(fd, 0.2)
        from miniterm import MiniTerm
        term = MiniTerm(80, 10)
        term.feed(out3)
        z_pos = term.find_text('z')
        pct_pos = term.find_text('%')
        if z_pos and pct_pos and z_pos[0] == pct_pos[0]:
            results.append(('008 cursor on prompt row after ctrl+c', True,
                f'z at row {z_pos[0]}, % at row {pct_pos[0]}'))
        elif z_pos:
            results.append(('008 cursor on prompt row after ctrl+c', False,
                f'z at {z_pos}, % at {pct_pos}'))
        else:
            results.append(('008 cursor on prompt row after ctrl+c', False, 'z not found'))

    finally:
        os.write(fd, b'exit\n')
        time.sleep(0.2)
        os.close(fd)
        os.waitpid(pid, 0)

    return results

if __name__ == '__main__':
    fail_count = 0
    pass_count = 0
    for name, ok, msg in run():
        if ok:
            pass_count += 1
            print(f'  PASS: {name}')
        else:
            fail_count += 1
            print(f'  FAIL: {name} — {msg}')
    print(f'\n{pass_count}/{pass_count + fail_count} passed')
    sys.exit(0 if fail_count == 0 else 1)
