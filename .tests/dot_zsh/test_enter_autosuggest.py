#!/usr/bin/env python3
"""
Consolidated: ghost, accept, enter cleanup, rapid enter, accept-and-hold, Esc+Enter.
# Time: ~24s (26 tests; 1 spawn).

Single spawn. All editing operations in one session.
"""
import os, sys, pty, select, time, re, subprocess, tempfile, shutil

# Session-wide byte accumulator: MiniTerm assertions that need the prompt
# symbol must replay the whole session (zle only emits screen diffs, so the
# prompt row may not be re-emitted in a partial window).
_session = {'data': b''}

def read_all(fd, timeout=0.5):
    global _session
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try:
            c = os.read(fd, 8192)
            if not c: break
            out += c
        except: break
    _session['data'] += out
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


def setup_dirty_repo():
    """Create a temp git repo with an untracked file (dirty -> color 88).
    Use short path under /tmp so prompt doesn't truncate dir name."""
    import random, string
    suffix = ''.join(random.choices(string.ascii_lowercase, k=6))
    tmpdir = f'/tmp/zsh_repo_{suffix}'
    subprocess.run(['git', 'init', '-b', 'main', tmpdir], capture_output=True)
    subprocess.run(['git', '-C', tmpdir, 'config', 'user.email', 'test@test'], capture_output=True)
    subprocess.run(['git', '-C', tmpdir, 'config', 'user.name', 'test'], capture_output=True)
    with open(os.path.join(tmpdir, 'init'), 'w') as f:
        f.write('init')
    subprocess.run(['git', '-C', tmpdir, 'add', 'init'], capture_output=True)
    subprocess.run(['git', '-C', tmpdir, 'commit', '-m', 'init'], capture_output=True)
    with open(os.path.join(tmpdir, 'untracked'), 'w') as f:
        f.write('dirty')
    return tmpdir


def wait_for_prompt(fd, timeout=3.0):
    """Wait until data arrives on fd. Returns True if data ready."""
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

def strip_ansi_data(data):
    """Aggressive strip for accept-and-hold / esc tests."""
    if isinstance(data, bytes): data = data.decode('latin-1')
    data = re.sub(r'\x1b\][^\x07\x1b]*[\x07\x1b\\]', '', data)
    data = re.sub(r'\x1b\[[\d;?]*[ABCDEFGHJKLMNPSTfghilmnrsu]', '', data)
    data = re.sub(r'\x1b.', '', data)
    data = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1a\x1c-\x1f]', '', data)
    return data.replace('\x07', '')

def run():
    dirty_repo = setup_dirty_repo()
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '10'
        d = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(d, exist_ok=True)
        cfg = f'cd {dirty_repo} 2>/dev/null\n'
        cfg += 'source ~/.zshrc 2>/dev/null || true\n'
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write(cfg)
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)

    results = []
    all_data = b''

    try:
        wait_for_prompt(fd, 2.0)
        read_all(fd, 0.2)

        # --- Phase 1: Ghost ---
        os.write(fd, b'echo hello\n')
        time.sleep(0.3)
        read_all(fd, 0.2)
        os.write(fd, b'echo ')
        time.sleep(0.5)
        out = read_all(fd, 0.2)
        vis = visible_lines(out)
        ghost_ok = any('hello' in l for l in vis)
        results.append(('001 ghost visible', ghost_ok, 'ghost not found'))

        # --- Cursor after ghost: Ctrl+L, 'x' types on same row as % ---
        os.write(fd, b'\x0c')
        time.sleep(0.3)
        out_redraw = read_all(fd, 0.2)
        os.write(fd, b'x')
        time.sleep(0.2)
        outx = out_redraw + read_all(fd, 0.2)
        from miniterm import MiniTerm
        term = MiniTerm(80, 10)
        term.feed(outx)
        x_pos = term.find_text('x')
        pct_pos = term.find_text('%')
        if x_pos and pct_pos and x_pos[0] == pct_pos[0]:
            results.append(('001b cursor on prompt row with ghost', True,
                f'x at row {x_pos[0]}, % at row {pct_pos[0]}'))
        elif x_pos:
            results.append(('001b cursor on prompt row with ghost', False,
                f'x at {x_pos}, % at {pct_pos}'))
        else:
            results.append(('001b cursor on prompt row with ghost', False, 'x not found'))

        # --- Phase 2: Footer before action ---
        os.write(fd, b'\x0c')
        time.sleep(0.3)
        out = read_all(fd, 0.2)
        vis = visible_lines(out)
        fc = count_footers(vis)
        results.append(('002 footer before action', fc >= 1, f'{fc} footers'))

        # --- Phase 2b: Partial accept (M-f = forward-word = partial_accept) ---
        # Footer may persist on screen from prior render; use Ctrl+L to force full redraw.
        os.write(fd, b'echo hello\n')
        time.sleep(0.3)
        read_all(fd, 0.2)
        os.write(fd, b'echo h')
        time.sleep(0.5)
        read_all(fd, 0.2)
        os.write(fd, b'\x1bf')  # M-f = forward-word
        time.sleep(0.3)
        read_all(fd, 0.2)
        os.write(fd, b'\x0c')  # Ctrl+L to force full redraw
        time.sleep(0.3)
        out = read_all(fd, 0.2)
        vis = visible_lines(out)
        fc_pa = count_footers(vis)
        results.append(('002b partial accept: one footer', fc_pa == 1, f'{fc_pa} footers'))
        colors = set(re.findall(rb'38;5;(\d+)', out))
        results.append(('002c partial accept: dir color 135', b'135' in colors, f'colors: {colors}'))
        # Branch color depends on git state of chezmoi (typically 88=dark red for untracked)
        has_branch_color = not colors.isdisjoint({b'34', b'88', b'208', b'220', b'112'})
        results.append(('002d partial accept: branch colored', has_branch_color, f'colors: {colors}'))

        # --- Phase 3: Accept suggestion (Ctrl+F) ---
        os.write(fd, b'echo hello world\n')
        time.sleep(0.3)
        read_all(fd, 0.2)
        os.write(fd, b'echo h')
        time.sleep(0.5)
        read_all(fd, 0.2)
        os.write(fd, b'\x06')
        time.sleep(0.3)
        read_all(fd, 0.2)
        os.write(fd, b'\x0c')
        time.sleep(0.3)
        out = read_all(fd, 0.2)
        vis = visible_lines(out)
        fc_accept = count_footers(vis)
        results.append(('003 accept: one footer', fc_accept == 1, f'{fc_accept} footers'))
        colors_ac = set(re.findall(rb'38;5;(\d+)', out))
        results.append(('003b accept: dir color 135', b'135' in colors_ac, f'colors: {colors_ac}'))
        has_bc = not colors_ac.isdisjoint({b'34', b'88', b'208', b'220', b'112'})
        results.append(('003c accept: branch colored', has_bc, f'colors: {colors_ac}'))

        # No color leak in buffer after accept
        text = out.decode('utf-8', errors='replace')
        has_buf_color = False
        for l in text.replace('\r\n', '\n').split('\n'):
            clean = l.replace('\x1b', 'ESC')
            if '%' in clean:
                reset_pos = clean.rfind('ESC[0m')
                buf = clean[reset_pos:] if reset_pos >= 0 else clean
                colors = re.findall(r'ESC\[[0-9;]*m', buf)
                disallowed = [c for c in colors if c not in ('ESC[0m','ESC[K')]
                if disallowed:
                    has_buf_color = True
                    break
        results.append(('004 accept: no buffer color', not has_buf_color, 'color leak'))

        # --- Phase 4: Raw Enter with ghost ---
        os.write(fd, b'echo hello\n')
        time.sleep(0.3)
        read_all(fd, 0.2)
        os.write(fd, b'echo h')
        time.sleep(0.5)
        read_all(fd, 0.2)
        os.write(fd, b'\n')
        time.sleep(0.3)
        out = read_all(fd, 0.2)
        vis = visible_lines(out)
        fc_enter = count_footers(vis)
        results.append(('005 enter with ghost: one footer', fc_enter == 1, f'{fc_enter} footers'))

        # --- Phase 5: Rapid enter ---
        for _ in range(3):
            os.write(fd, b'\n')
            time.sleep(0.15)
        out = read_all(fd, 0.2)
        vis = visible_lines(out)
        fc_rapid = count_footers(vis)
        results.append(('006 rapid enter: footer present', fc_rapid >= 1, f'{fc_rapid} footers'))

        # --- Phase 6: Accept-and-hold (Alt+A) ---
        os.write(fd, b'echo 88\n')
        time.sleep(0.3)
        read_all(fd, 0.2)
        os.write(fd, b'echo 88')
        time.sleep(0.15)
        all_data += read_all(fd, 0.15)
        os.write(fd, b'\x1ba')
        time.sleep(0.8)
        all_data += read_all(fd, 0.5)
        time.sleep(0.3)
        all_data += read_all(fd, 0.3)

        # Find intrusive footers between echo and output
        echo_pos = max(all_data.rfind(b'echo 88'), all_data.rfind(b'88'))
        output_pos = max(all_data.rfind(b'\n88\r\n'), all_data.rfind(b'88\r\n'))
        if echo_pos < 0: echo_pos = 0
        if output_pos < 0: output_pos = len(all_data)

        idx = 0
        intrusive = 0
        while True:
            p = all_data.find(b'\x1b[1B\r', idx)
            if p < 0: break
            next_byte = all_data[p + 5:p + 6] if p + 5 < len(all_data) else b''
            if next_byte not in (b'\r', b'\n') and echo_pos < p < output_pos:
                intrusive += 1
            idx = p + 5
        results.append(('007 accept-and-hold: no intrusive footer', intrusive == 0,
            f'{intrusive} footer(s) between echo and output'))
        ac_colors = set(re.findall(rb'38;5;(\d+)', all_data))
        results.append(('007b accept-and-hold: dir color 135', b'135' in ac_colors,
            f'colors: {ac_colors}'))
        has_bc2 = not ac_colors.isdisjoint({b'34', b'88', b'208', b'220', b'112'})
        results.append(('007c accept-and-hold: branch colored', has_bc2, f'colors: {ac_colors}'))

        # Clear held line
        os.write(fd, b'\n')
        time.sleep(0.3)
        read_all(fd, 0.2)

        # --- Phase 7: Esc+Enter ---
        os.write(fd, b'echo 123')
        time.sleep(0.15)
        all_data += read_all(fd, 0.15)
        os.write(fd, b'\033\r')
        time.sleep(0.5)
        all_data += read_all(fd, 0.3)
        os.write(fd, b'\n')
        time.sleep(0.5)
        all_data += read_all(fd, 0.5)

        text = strip_ansi_data(all_data)
        lines = text.split('\n')
        echo_idx = None
        pct_indices = []
        for i, l in enumerate(lines):
            if 'echo 123' in l:
                echo_idx = i
            if l.strip().startswith('%'):
                pct_indices.append(i)

        blank_excess = False
        if echo_idx is not None:
            next_pct = None
            for i in pct_indices:
                if i > echo_idx:
                    next_pct = i
                    break
            if next_pct is not None:
                between = lines[echo_idx + 1:next_pct]
                blank = sum(1 for l in between if not l.strip())
                if blank > 1:
                    blank_excess = True
        results.append(('008 esc+enter: no excess blank line', not blank_excess,
            'excess blank lines'))

        # --- Cursor after Esc+Enter: Ctrl+L, 'w' types on same row as % ---
        os.write(fd, b'\x0c')
        time.sleep(0.3)
        out_redraw = read_all(fd, 0.2)
        os.write(fd, b'w')
        time.sleep(0.2)
        outw = out_redraw + read_all(fd, 0.2)
        term = MiniTerm(80, 10)
        term.feed(outw)
        w_pos = term.find_text('w')
        pct_pos = term.find_text('%')
        if w_pos and pct_pos and w_pos[0] == pct_pos[0]:
            results.append(('009 cursor on prompt row after esc+enter', True,
                f'w at row {w_pos[0]}, % at row {pct_pos[0]}'))
        elif w_pos:
            results.append(('009 cursor on prompt row after esc+enter', False,
                f'w at {w_pos}, % at {pct_pos}'))
        else:
            results.append(('009 cursor on prompt row after esc+enter', False, 'w not found'))

        # --- Phase 8: Tab completion (expand-or-complete) ---
        os.write(fd, b'cd /tm')
        time.sleep(0.2)
        read_all(fd, 0.15)
        os.write(fd, b'\t')  # Tab
        time.sleep(0.5)
        read_all(fd, 0.3)
        os.write(fd, b'\x0c')  # Ctrl+L to see full state after completion
        time.sleep(0.3)
        out_tab = read_all(fd, 0.3)
        vis_tab = visible_lines(out_tab)
        fc_tab = count_footers(vis_tab)
        results.append(('010 tab complete: footer present', fc_tab >= 1, f'{fc_tab} footers'))
        text_tab_raw = out_tab.decode('utf-8', errors='replace')
        text_tab_clean = strip_ansi(text_tab_raw)
        completed = '/tmp/' in text_tab_clean
        results.append(('011 tab complete: path completed', completed,
            f'clean: {text_tab_clean[-80:]!r}'))

        # Tab again to verify a second completion keeps footer
        os.write(fd, b'\x15')  # Ctrl+U to clear any stale buffer
        time.sleep(0.1)
        read_all(fd, 0.1)
        os.write(fd, b'cd /tm')
        time.sleep(0.2)
        read_all(fd, 0.15)
        # --- 012a: first Tab completes /tm -> /tmp/ uniquely: no list is
        # rendered, so the footer must stay visible. Bug: the wrap hid the
        # footer before every completion, so it vanished on a unique insert
        # (only visible with autosuggest, whose zle -R clears the stale row).
        os.write(fd, b'\t')
        time.sleep(0.5)
        read_all(fd, 0.3)
        t1_mark = len(_session['data'])
        term_t1 = MiniTerm(80, 10)
        term_t1.feed(_session['data'][:t1_mark])
        # the footer elides the middle of long paths, so match the unique
        # random suffix instead of the full repo path
        repo_suffix = dirty_repo.rsplit('_', 1)[-1]
        t1_footer = any(repo_suffix in r for r in term_t1.display)
        results.append(('012a unique Tab inserts, footer stays', t1_footer,
                        'footer hidden after unique Tab (no list shown)'))
        os.write(fd, b'\t')  # second Tab: /tmp list -> y/n question
        time.sleep(0.5)
        read_all(fd, 0.3)
        # --- 012b: y/n question state: footer must be hidden ---
        # Bug (autosuggest): the completion restored the footer text into
        # POSTDISPLAY mid-completion, so the footer stayed visible (grey)
        # during the y/n question instead of hiding.
        q_mark = len(_session['data'])
        term_q = MiniTerm(80, 10)
        term_q.feed(_session['data'][:q_mark])
        q_visible = any('do you wish' in r for r in term_q.display)
        q_footer = any(repo_suffix in r for r in term_q.display)
        if q_visible:
            results.append(('012b y/n question: footer hidden', not q_footer,
                            'footer visible during question'))
        else:
            results.append(('012b y/n question: footer hidden', True,
                            'no y/n question shown (env)'))
        # first Ctrl+L may be swallowed by the y/n question ('n' answer);
        # the second clear-screen always runs as a widget, clearing the menu
        # state and restoring the footer
        os.write(fd, b'\x0c')
        time.sleep(0.3)
        read_all(fd, 0.2)
        # --- 012c: right after the 'n' answer the footer must be hidden ---
        # (the bug drew it grey via autosuggest's restored POSTDISPLAY)
        n_mark = len(_session['data'])
        term_n = MiniTerm(80, 10)
        term_n.feed(_session['data'][:n_mark])
        n_footer = any(repo_suffix in r for r in term_n.display)
        if q_visible:
            results.append(('012c after n answer: footer hidden (not grey)', not n_footer,
                            'grey footer visible after n'))
        else:
            results.append(('012c after n answer: footer hidden (not grey)', True,
                            'no y/n question shown (env)'))
        os.write(fd, b'\x0c')
        time.sleep(0.3)
        out_tab2 = read_all(fd, 0.3)
        vis_tab2 = visible_lines(out_tab2)
        fc_tab2 = count_footers(vis_tab2)
        results.append(('012 tab complete x2: footer present', fc_tab2 >= 1, f'{fc_tab2} footers'))

        # --- Cursor after Tab: Ctrl+L, 'u' types on same row as % ---
        # NOTE: the first Ctrl+L may be swallowed by a "do you wish" y/n
        # question (130 matches under /tm), so the prompt row is only
        # guaranteed in the full-session replay.
        os.write(fd, b'\x0c')
        time.sleep(0.3)
        read_all(fd, 0.2)
        os.write(fd, b'u')
        time.sleep(0.2)
        read_all(fd, 0.2)
        term = MiniTerm(80, 10)
        term.feed(_session['data'])
        u_pos = term.find_text('u')
        # prefer the % on the u row (active prompt); a stale % may linger
        # on an earlier row (prompt redraw artifact)
        pct_pos_tab = None
        if u_pos:
            c = term.display[u_pos[0]].find('%')
            if c >= 0:
                pct_pos_tab = (u_pos[0], c)
        if pct_pos_tab is None:
            pct_pos_tab = term.find_text('%')
        if u_pos and pct_pos_tab and u_pos[0] == pct_pos_tab[0]:
            results.append(('013 cursor on prompt row after tab', True,
                f'u at row {u_pos[0]}, % at row {pct_pos_tab[0]}'))
        elif u_pos:
            results.append(('013 cursor on prompt row after tab', False,
                f'u at {u_pos}, % at {pct_pos_tab}'))
        else:
            results.append(('013 cursor on prompt row after tab', False, 'u not found'))

        # --- Phase 9: Autosuggest completes from recent history ---
        # echo 1234567890 → Enter → echo a → Enter → echo 1 + Ctrl+F → echo 1234567890
        os.write(fd, b'\x15')  # Ctrl+U to clear any stale buffer (from Phase 8 cursor test)
        time.sleep(0.1)
        read_all(fd, 0.1)
        os.write(fd, b'echo 1234567890\n')
        time.sleep(0.2)
        read_all(fd, 0.15)
        os.write(fd, b'echo a\n')
        time.sleep(0.2)
        read_all(fd, 0.15)
        os.write(fd, b'echo 1')
        time.sleep(0.15)
        out_ghost = read_all(fd, 0.1)
        # Ghost text uses color 90 (dim); check incremental output
        ghost_90 = b'38;5;90' in out_ghost or b'\x1b[90' in out_ghost
        results.append(('014b history ghost: dim color 90', ghost_90,
            f'ghost: {out_ghost[-40:]!r}'))
        os.write(fd, b'\x06')  # Ctrl+F (forward-char → autosuggest-accept)
        time.sleep(0.15)
        out_accept = read_all(fd, 0.15)
        clean = re.sub(b'\x1b' + br'\[[0-9;]*[a-zA-Z]', b'', out_accept)
        inc_890 = b'234567890' in clean
        results.append(('014 history accept: completes echo 1234567890', inc_890,
            f'clean: {clean[-30:]!r}'))
        # After accept, footer should still be present (dir=135, branch=88).
        # zle only emits screen diffs, so the colors appear in earlier bytes;
        # check the final rendered screen via full-session replay.
        term = MiniTerm(80, 10)
        term.feed(_session['data'])
        footer_ok = False
        detail = 'no footer row'
        for i in range(term.rows - 1, -1, -1):
            line = term.display[i]
            if line.strip():
                if 'main' in line:
                    bpos = line.find('main')
                    footer_ok = term.fg_at(i, 0) == 135 and term.fg_at(i, bpos) == 88
                    detail = f'row {i}: dir fg {term.fg_at(i, 0)}, main fg {term.fg_at(i, bpos)}'
                break
        results.append(('014c history accept: footer present (dir 135, branch 88)', footer_ok, detail))
        os.write(fd, b'\n')
        time.sleep(0.2)
        out_final = read_all(fd, 0.2)
        has_890 = b'1234567890' in out_final
        results.append(('015 history accept: output has 1234567890', has_890,
            f'out: {out_final[-60:]!r}'))

        # Ctrl+L to force full redraw; check footer colors
        os.write(fd, b'\x0c')
        time.sleep(0.3)
        out_redraw = read_all(fd, 0.2)
        rd_135 = b'38;5;135' in out_redraw
        rd_88 = b'38;5;88' in out_redraw
        results.append(('015b history redraw: footer dir color 135', rd_135,
            f'redraw: {out_redraw[-40:]!r}'))
        results.append(('015c history redraw: footer branch colored', rd_88,
            f'redraw: {out_redraw[-40:]!r}'))

    finally:
        os.write(fd, b'exit\n')
        time.sleep(0.2)
        os.close(fd)
        os.waitpid(pid, 0)
        shutil.rmtree(dirty_repo, ignore_errors=True)

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
