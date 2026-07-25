#!/usr/bin/env python3
"""
RED tests for:
1. Ctrl+C red % should revert to white after successful command
2. Async git untracked should update branch from green to red after cd to dirty repo
"""
import os, sys, pty, select, time, re, tempfile, shutil

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

def spawn_real(config='source ~/.zshrc 2>/dev/null || true', lines=24, cwd=None):
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'; os.environ['LINES'] = str(lines)
        d = f'/tmp/zsh_rtest_{os.getpid()}'; os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config + '\n')
        with open(os.path.join(d, '.zshenv'), 'w') as f: f.write('export ZDOTDIR="$HOME"\n')
        os.environ['ZDOTDIR'] = d
        if cwd:
            os.chdir(cwd)
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)
    return pid, fd

pass_count = 0
fail_count = 0
CHEZMOI_DIR = os.path.expanduser('~/.local/share/chezmoi')

def test(fn):
    global pass_count, fail_count
    name = fn.__doc__.strip() if fn.__doc__ else fn.__name__
    ok, msg = False, 'exception'
    try: ok, msg = fn()
    except Exception as e: msg = str(e)
    if ok: pass_count += 1; print(f'  PASS: {name}')
    else: fail_count += 1; print(f'  FAIL: {name} — {msg}')

# ===== Bug 1: Ctrl+C red % persists after successful command =====

def _red_ctrlc_then_good():
    """Ctrl+C shows red %, then successful command shows white %."""
    pid, fd = spawn_real(lines=10)
    time.sleep(0.8); read_all(fd, 0.5)

    # Ctrl+C → should show red %
    os.write(fd, b'\x03'); time.sleep(0.5)
    read_all(fd, 1.0)

    # Successful command — the new prompt should show white %
    os.write(fd, b'echo ok\n'); time.sleep(0.8)
    out = read_all(fd, 1.0)

    pct_idx = out.rfind(b'%')
    if pct_idx < 0:
        os.close(fd); os.waitpid(pid, 0)
        return False, '% not found after successful command'

    prefix = out[max(0, pct_idx-80):pct_idx]
    colors = re.findall(rb'\x1b\[([0-9;]*)m', prefix)
    has_red = any(b'38;5;196' in c or c == b'91' or c == b'101' for c in colors)

    os.close(fd); os.waitpid(pid, 0)
    if has_red:
        return False, '% is still red after successful command'
    return True, '% returned to white'

# ===== Bug 2: Async untracked should turn branch red after cd =====

def _async_untracked_green_to_red():
    """Branch turns from green to red after cd to untracked repo (triggered by keypress)."""
    if not os.path.isdir(CHEZMOI_DIR):
        return False, f'chezmoi dir not found: {CHEZMOI_DIR}'

    clean_repo = tempfile.mkdtemp(prefix='clean_repo_')
    try:
        ret = os.system(f'''
cd {clean_repo}
git init -q
git config user.email test@test
git config user.name test
echo "clean" > readme.txt
git add readme.txt
git commit -q -m init 2>/dev/null
''')
        if ret != 0:
            return False, 'failed to create clean git repo'

        pid, fd = spawn_real(lines=24, cwd=clean_repo)
        time.sleep(1.0); read_all(fd, 0.5)

        # Cd to chezmoi (has untracked files)
        os.write(fd, f'cd {CHEZMOI_DIR}\n'.encode())
        time.sleep(2.0)  # wait for async completion + USR1

        # Press Enter to flush any queued .reset-prompt redraw
        read_all(fd, 0.2)  # drain available output
        os.write(fd, b'\n')
        time.sleep(0.8)
        out = read_all(fd, 1.0)

        text = out.decode('utf-8', errors='replace').replace('\x1b', 'ESC')
        has_dark_red = 'ESC[38;5;88m' in text or re.search(r'38;5;88', text) is not None

        os.close(fd); os.waitpid(pid, 0)
        if not has_dark_red:
            return False, 'dark red (88) not found after cd to chezmoi + Enter'
        return True, 'branch turned red (88) after cd'
    finally:
        shutil.rmtree(clean_repo, ignore_errors=True)

def main():
    print('RED tests: Ctrl+C red persists + async untracked')
    for fn in [_red_ctrlc_then_good, _async_untracked_green_to_red]:
        test(fn)
    print(f'\n{pass_count}/{pass_count + fail_count} passed')
    sys.exit(0 if fail_count == 0 else 1)

if __name__ == '__main__':
    main()
