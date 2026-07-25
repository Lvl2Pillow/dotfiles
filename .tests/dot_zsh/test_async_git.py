#!/usr/bin/env python3
"""
Consolidated: async git color updates.
# Time: ~15s (7 tests; 3 spawns).

Single spawn. Cd to chezmoi (dirty repo), wait for async, check:
- Color 88 (dark red) appears in output BEFORE any keystroke
- Branch name visible in footer
- No stale green (34) from previous clean state
"""
import os, sys, pty, select, time, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.venv', 'lib',
    f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages'))

CHEZMOI = os.path.expanduser('~/.local/share/chezmoi')

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

def branch_colors_in_output(out):
    colors = set()
    for c in re.findall(rb'38;5;(\d+)', out):
        colors.add(c.decode())
    return colors

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
        final = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', final_text).strip()
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

def run():
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '24'
        d = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(d, exist_ok=True)
        cfg = f'cd ~ 2>/dev/null\n'  # start in home (non-git or clean context)
        cfg += 'source ~/.zshrc 2>/dev/null || true\n'
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write(cfg)
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)

    results = []

    try:
        time.sleep(1.0)
        read_all(fd, 0.5)

        # cd to chezmoi (dirty repo with untracked/staged changes)
        os.write(fd, f'cd {CHEZMOI}\n'.encode())
        time.sleep(0.2)

        # Wait for async to complete
        time.sleep(2.0)  # async completion

        # Capture output WITHOUT any keystroke — zle .redisplay updates colors
        out = read_all(fd, 1.0)
        colors = branch_colors_in_output(out)

        has_88 = '88' in colors
        results.append(('001 async: dark red (88) without keystroke', has_88, f'colors: {colors}'))

        # Branch name should be visible somewhere
        branch_text = b'main' in out or b'chezmoi' in out
        results.append(('002 async: branch visible', branch_text, 'branch not in output'))

        # Green (34) should NOT be the last branch color — 88 should dominate
        # Check if 88 appears after 34 in the output
        if has_88:
            last_34 = out.rfind(b'38;5;34')
            last_88 = out.rfind(b'38;5;88')
            green_stale = last_34 > last_88
            results.append(('003 async: no stale green after red', not green_stale,
                f'last 34 at {last_34}, last 88 at {last_88}'))

        # --- Cursor after async: Ctrl+L, 'q' types on same row as % ---
        os.write(fd, b'\x0c')
        time.sleep(0.3)
        out_redraw = read_all(fd, 0.2)
        os.write(fd, b'q')
        time.sleep(0.2)
        out_q = out_redraw + read_all(fd, 0.2)
        from miniterm import MiniTerm
        term = MiniTerm(80, 10)
        term.feed(out_q)
        q_pos = term.find_text('q')
        pct_pos = term.find_text('%')
        if q_pos and pct_pos and q_pos[0] == pct_pos[0]:
            results.append(('004 async cursor on prompt row', True,
                f'q at row {q_pos[0]}, % at row {pct_pos[0]}'))
        elif q_pos:
            results.append(('004 async cursor on prompt row', False,
                f'q at {q_pos}, % at {pct_pos}'))
        else:
            results.append(('004 async cursor on prompt row', False, 'q not found'))

    finally:
        os.write(fd, b'exit\n')
        time.sleep(0.2)
        os.close(fd)
        os.waitpid(pid, 0)

    return results


def run_rapid_cd():
    """Rapid cd: cd to dirty, wait, cd to clean, check final state is clean.
    Second async invalidates first via counter mismatch."""
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '24'
        d = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(d, exist_ok=True)
        cfg = f'cd ~ 2>/dev/null\n'
        cfg += 'source ~/.zshrc 2>/dev/null || true\n'
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write(cfg)
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)

    results = []

    try:
        time.sleep(1.0)
        read_all(fd, 0.5)

        # cd to dirty repo, wait for async to complete
        os.write(fd, f'cd {CHEZMOI}\n'.encode())
        time.sleep(2.0)
        read_all(fd, 0.3)

        # Capture output with dirty repo state
        out_dirty = read_all(fd, 0.3)
        colors_dirty = branch_colors_in_output(out_dirty)

        # Immediately cd to /tmp (non-git dir, no branch)
        os.write(fd, b'cd /tmp\n')
        time.sleep(0.3)
        # Don't wait for full async — just check interim state
        read_all(fd, 0.3)

        # Type 'echo x' to generate a new prompt with rendered footer
        os.write(fd, b'echo x\n')
        time.sleep(0.5)
        out_final = read_all(fd, 0.3)

        # After cd to /tmp, there should be NO git branch in footer
        text = out_final.decode('utf-8', errors='replace')
        has_git_branch = bool(re.search(r'chezmoi|main|master', text, re.I))
        results.append(('004 rapid cd: no stale branch after cd to non-git', not has_git_branch,
            f'stale branch found in: {text[:200]}'))

    finally:
        os.write(fd, b'exit\n')
        time.sleep(0.2)
        os.close(fd)
        os.waitpid(pid, 0)

    return results


def run_no_autosuggest():
    """Without zsh-autosuggestions, accept-line wrapper cleans footer."""
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '10'
        d = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(d, exist_ok=True)
        # Minimal config: prompt only, no autosuggestions loaded
        prompt_file = os.path.expanduser('~/.local/share/chezmoi/dot_zsh/05_prompt.zsh')
        cfg = f'cd /tmp 2>/dev/null\n'
        cfg += f'_PROMPT_FORCE_LOAD=1; source "{prompt_file}"\n'
        cfg += 'unset _PROMPT_FORCE_LOAD\n'
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write(cfg)
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)

    results = []

    try:
        time.sleep(1.0)
        read_all(fd, 0.5)

        # Type a command, press Enter
        os.write(fd, b'echo hi\n')
        time.sleep(0.5)
        out = read_all(fd, 0.3)
        vis = visible_lines(out)
        fc = count_footers(vis)
        results.append(('005 no-autosuggest: footer after Enter', fc == 1,
            f'{fc} footers'))

        # Enter on empty buffer should show clean prompt
        os.write(fd, b'\n')
        time.sleep(0.3)
        out = read_all(fd, 0.2)
        vis = visible_lines(out)
        fc2 = count_footers(vis)
        results.append(('006 no-autosuggest: footer on empty Enter', fc2 == 1,
            f'{fc2} footers'))

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
    for name, ok, msg in run_rapid_cd():
        if ok:
            pass_count += 1
            print(f'  PASS: {name}')
        else:
            fail_count += 1
            print(f'  FAIL: {name} — {msg}')
    for name, ok, msg in run_no_autosuggest():
        if ok:
            pass_count += 1
            print(f'  PASS: {name}')
        else:
            fail_count += 1
            print(f'  FAIL: {name} — {msg}')
    print(f'\n{pass_count}/{pass_count + fail_count} passed')
    sys.exit(0 if fail_count == 0 else 1)
