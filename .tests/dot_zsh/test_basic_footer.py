#!/usr/bin/env python3
"""
Consolidated: footer rendering + permission denied + cursor position.
# Time: ~6s (11 tests; 1 spawn).

Single spawn. Footer visible, symbol, long buffer, no duplicate,
no permission denied from unreadable .git, cursor after % prompt.
"""
import os, sys, pty, select, time, re, tempfile, shutil, subprocess

from miniterm import MiniTerm

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

def poll_for(fd, check_fn, timeout=5.0, interval=0.05):
    """Read from fd until check_fn(data) returns True or timeout.
    Returns all data read."""
    deadline = time.time() + timeout
    data = b''
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], interval)
        if r:
            try:
                chunk = os.read(fd, 8192)
                if chunk:
                    data += chunk
            except:
                pass
        if check_fn(data):
            break
    return data


def wait_for_prompt(fd, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r: return True
    return False

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

def setup_clean_repo():
    """Create a temp clean git repo (no dirty state -> color 34)."""
    tmpdir = tempfile.mkdtemp(prefix='zsh_test_repo_')
    subprocess.run(['git', 'init', '-b', 'main', tmpdir], capture_output=True)
    subprocess.run(['git', '-C', tmpdir, 'config', 'user.email', 'test@test'], capture_output=True)
    subprocess.run(['git', '-C', tmpdir, 'config', 'user.name', 'test'], capture_output=True)
    with open(os.path.join(tmpdir, 'init'), 'w') as f:
        f.write('init')
    subprocess.run(['git', '-C', tmpdir, 'add', 'init'], capture_output=True)
    subprocess.run(['git', '-C', tmpdir, 'commit', '-m', 'init'], capture_output=True)
    return tmpdir


def run():
    clean_repo = setup_clean_repo()
    perm_dir = tempfile.mkdtemp(prefix='zsh_perm_')
    nested = os.path.join(perm_dir, 'a', 'b', 'c')
    os.makedirs(nested)
    gitfile = os.path.join(nested, '.git')
    with open(gitfile, 'w') as f:
        f.write('gitdir: /nonexistent\n')
    os.chmod(gitfile, 0o000)
    parent_git = os.path.join(perm_dir, 'a', '.git')
    os.makedirs(os.path.join(parent_git, 'objects'))
    with open(os.path.join(parent_git, 'HEAD'), 'w') as f:
        f.write('ref: refs/heads/main\n')

    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '10'
        d = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(d, exist_ok=True)
        cfg = 'cd /tmp 2>/dev/null\nsource ~/.zshrc 2>/dev/null || true\n'
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write(cfg)
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)

    results = []

    try:
        wait_for_prompt(fd, 2.0)
        out = read_all(fd, 0.2)
        vis = visible_lines(out)

        fc = count_footers(vis)
        results.append(('001 footer visible', fc >= 1, f'0 footers'))
        results.append(('002 single footer', fc <= 1, f'{fc} footers'))
        has_symbol = any('%' in l for l in vis)
        results.append(('003 prompt symbol visible', has_symbol, 'no % found'))
        # RED: dir/branch with %% must not be interpreted as prompt escape
        # Footer text should show literal % (e.g. ~/50%off), not consume it
        for l in vis:
            stripped_ansi = re.sub(r'\x1b\[[0-9;]*m', '', l)
            if '~' in stripped_ansi or '/' in stripped_ansi:
                if '%' in stripped_ansi and '%%' not in stripped_ansi:
                    results.append(('003b literal % in footer', False,
                        f'bare % found in: {stripped_ansi}'))
                    break
        else:
            results.append(('003b literal % in footer', True, 'no bare %'))

        os.write(fd, b'echo ' + b'a' * 120)
        time.sleep(0.15)
        out = read_all(fd, 0.15)
        vis = visible_lines(out)
        has_long = any('aaaa' in l for l in vis)
        results.append(('004 long buffer text visible', has_long, 'aaaa not found'))

        os.write(fd, b'\n')
        time.sleep(0.3)
        out = read_all(fd, 0.2)
        vis = visible_lines(out)
        fc2 = count_footers(vis)
        results.append(('005 footer after command', fc2 == 1, f'{fc2} footers'))

        # Permission denied
        os.write(fd, f'cd {nested}\n'.encode())
        time.sleep(0.3)
        out = read_all(fd, 0.2)
        err_text = out.decode('utf-8', errors='replace').lower()
        has_perm_err = 'permission denied' in err_text
        results.append(('006 no permission denied from .git', not has_perm_err,
            'permission denied found'))

        # Cursor position: cd to clean repo, press Enter, type x, check cursor
        os.write(fd, f'cd {clean_repo}\n'.encode())
        poll_for(fd, lambda d: b'38;5;34' in d, timeout=5.0)
        os.write(fd, b'\n')
        time.sleep(0.3)
        out_before = read_all(fd, 0.2)
        os.write(fd, b'x')
        time.sleep(0.2)
        out = out_before + read_all(fd, 0.2)

        term = MiniTerm(80, 10)
        term.feed(out)
        x_row = -1
        x_col = -1
        for i, line in enumerate(term.display):
            if 'x' in line:
                x_row = i
                x_col = line.find('x')
                break
        # The active prompt is the one on the typed char's row; a stale '%'
        # may linger on an earlier row (prompt redraw artifact), so prefer
        # the % adjacent to x.
        pct_row = -1
        pct_col = -1
        if x_row >= 0:
            c = term.display[x_row].find('%')
            if c >= 0:
                pct_row, pct_col = x_row, c
        if pct_row < 0:
            for i, line in enumerate(term.display):
                if '%' in line:
                    pct_row = i
                    pct_col = line.find('%')
                    break

        if x_row < 0:
            results.append(('007 cursor position', False, 'x not found'))
        elif pct_row < 0 and x_col <= 3:
            results.append(('007 cursor position', True, f'x at col {x_col}, near % '))
        elif x_row == pct_row and abs(x_col - (pct_col + 2)) <= 2:
            results.append(('007 cursor position', True, f'x at col {x_col} after % '))
        else:
            results.append(('007 cursor position', False,
                f'x at ({x_row},{x_col}), % at ({pct_row},{pct_col})'))

        # --- Color check: footer dir purple (135), branch green (34) ---
        colors = set(re.findall(rb'38;5;(\d+)', out))
        results.append(('008 footer dir color 135', b'135' in colors, f'colors: {colors}'))
        results.append(('009 footer branch color 34', b'34' in colors, f'colors: {colors}'))

        # --- Cursor after cd+Enter: Ctrl+L, type 'y', check same row as % ---
        os.write(fd, b'\x0c')
        time.sleep(0.3)
        out_redraw = read_all(fd, 0.2)
        os.write(fd, b'y')
        time.sleep(0.2)
        out2 = out_redraw + read_all(fd, 0.2)
        term2 = MiniTerm(80, 10)
        term2.feed(out2)
        y_pos = term2.find_text('y')
        # prefer the % on the y row (active prompt), like 007
        pct2 = None
        if y_pos:
            c = term2.display[y_pos[0]].find('%')
            if c >= 0:
                pct2 = (y_pos[0], c)
        if pct2 is None:
            pct2 = term2.find_text('%')
        if y_pos and pct2 and y_pos[0] == pct2[0]:
            results.append(('010 cursor on prompt row after cd', True,
                f'y at row {y_pos[0]}, % at row {pct2[0]}'))
        elif y_pos:
            results.append(('010 cursor on prompt row after cd', False,
                f'y at {y_pos}, % at {pct2}'))
        else:
            results.append(('010 cursor on prompt row after cd', False, 'y not found'))

    finally:
        os.write(fd, b'exit\n')
        time.sleep(0.2)
        os.close(fd)
        os.waitpid(pid, 0)
        shutil.rmtree(perm_dir, ignore_errors=True)
        shutil.rmtree(clean_repo, ignore_errors=True)

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
