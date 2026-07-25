#!/usr/bin/env python3
"""
Consolidated region_highlight probe. Covers accumulation, mid-buffer edit,
accept, different prefix lengths, and Ctrl+L. Run with the real prompt loaded.

Uses a custom keybinding (F2) to dump region_highlight state to a temp file.
"""
import os, sys, pty, select, time, subprocess, shutil, random, string, tempfile

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c if c else b''
        except: break
    return out

def setup_dirty_repo():
    suffix = ''.join(random.choices(string.ascii_lowercase, k=6))
    tmpdir = f'/tmp/zsh_repo_{suffix}'
    subprocess.run(['git', 'init', '-b', 'main', tmpdir], capture_output=True)
    subprocess.run(['git', '-C', tmpdir, 'config', 'user.email', 'test@test'], capture_output=True)
    subprocess.run(['git', '-C', tmpdir, 'config', 'user.name', 'test'], capture_output=True)
    with open(os.path.join(tmpdir, 'init'), 'w') as f: f.write('init')
    subprocess.run(['git', '-C', tmpdir, 'add', 'init'], capture_output=True)
    subprocess.run(['git', '-C', tmpdir, 'commit', '-m', 'init'], capture_output=True)
    with open(os.path.join(tmpdir, 'untracked'), 'w') as f: f.write('dirty')
    return tmpdir

def wait_for_prompt(fd):
    deadline = time.time() + 3.0
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r: return True
    return False

def poll_file(path, check_fn, timeout=5.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with open(path) as f: content = f.read()
            if check_fn(content): return content
        except: pass
        time.sleep(interval)
    try:
        with open(path) as f: return f.read()
    except: return ''

def probe_state(fd, probe_file):
    """Write probe key (F2) and wait for dump to appear in probe_file."""
    open(probe_file, 'w').close()
    os.write(fd, b'\x1b[1;2P')  # probe key
    time.sleep(0.4)
    return poll_file(probe_file, lambda c: 'END' in c)

def spawn(dirty_repo, probe_file, cfg_extra=()):
    """Spawn zsh with a probe keybinding. Returns (pid, fd)."""
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '10'
        d = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(d, exist_ok=True)

        cfg = [
            f'cd {dirty_repo} 2>/dev/null',
            'source ~/.zshrc 2>/dev/null || true',
            '',
            f'_PROBE_FILE={probe_file!r}',
            '_probe_rh() {',
            '  local IFS=$"\\n"',
            '  echo "WIDGET=$WIDGET" >> $_PROBE_FILE',
            '  echo "BUFFER_LEN=${#BUFFER}" >> $_PROBE_FILE',
            '  echo "POSTDISPLAY_LEN=${#POSTDISPLAY}" >> $_PROBE_FILE',
            '  echo "_prompt_dir_len=$_prompt_dir_len" >> $_PROBE_FILE',
            '  echo "RH_POS=$_prompt_rh_positions" >> $_PROBE_FILE',
            '  echo "RH:" >> $_PROBE_FILE',
            '  echo "${(F)region_highlight}" >> $_PROBE_FILE',
            '  echo "END" >> $_PROBE_FILE',
            '}',
            'zle -N _probe_rh',
            'bindkey "^[[1;2P" _probe_rh',
        ]
        cfg.extend(cfg_extra)
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write('\n'.join(cfg) + '\n')
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)
    return pid, fd

def count_own_rh_entries(content):
    """Count dir/branch entries (non-ghost, non-autosuggest)."""
    count = 0
    for line in content.split('\n'):
        if 'memo=prompt-footer' in line:
            count += 1
    return count

def run():
    dirty_repo = setup_dirty_repo()
    probe_file = tempfile.mktemp(prefix='zsh_rh_')

    pid, fd = spawn(dirty_repo, probe_file)
    try:
        wait_for_prompt(fd)
        read_all(fd, 0.2)

        # Warm up: run two commands to establish history and let async settle
        os.write(fd, b'echo 1234567890\n')
        time.sleep(0.3); read_all(fd, 0.2)
        os.write(fd, b'echo a\n')
        time.sleep(0.3); read_all(fd, 0.2)
        os.write(fd, b'echo b\n')
        time.sleep(0.4); read_all(fd, 0.2)

        # ---- SCENARIO 1: Accumulation ----
        # Type "echo 1" character by character, probe after each
        print("=== SCENARIO 1: Accumulation per keystroke ===")
        for ch in b'echo 1':
            os.write(fd, bytes([ch]))
            time.sleep(0.3)
            read_all(fd, 0.15)
            content = probe_state(fd, probe_file)
            if content:
                rh_count = count_own_rh_entries(content)
                buf_len = None
                for l in content.split('\n'):
                    if l.startswith('BUFFER_LEN='):
                        buf_len = l.split('=')[1]
                print(f"After '{chr(ch)}': BUFFER_LEN={buf_len} own_entries={rh_count}")
                # Show our entries
                for l in content.split('\n'):
                    if 'memo=prompt-footer' in l:
                        print(f"  {l}")

        # ---- SCENARIO 2: Mid-buffer insert ----
        # Now buffer is "echo 1" (len 6). Move cursor back to position 2 and insert "XYZ"
        print("\n=== SCENARIO 2: Mid-buffer insert ===")
        # First clear and type something with room to edit
        os.write(fd, b'\x03')  # Ctrl+C to clear
        time.sleep(0.3); read_all(fd, 0.2)

        os.write(fd, b'echo foobar')
        time.sleep(0.4); read_all(fd, 0.2)

        content = probe_state(fd, probe_file)
        print("Before mid-buffer edit:")
        if content:
            for l in content.split('\n'):
                if 'memo=prompt-footer' in l:
                    print(f"  {l}")

        # Move cursor to position 5 (after "echo ") and insert "XYZ"
        for _ in range(5):  # 5 left-arrows to go from end to position 5
            os.write(fd, b'\x1b[D')
            time.sleep(0.1)
        os.write(fd, b'XYZ')
        time.sleep(0.3); read_all(fd, 0.2)

        content = probe_state(fd, probe_file)
        print("After inserting 'XYZ' at position 5:")
        if content:
            buf_len = None
            for l in content.split('\n'):
                if l.startswith('BUFFER_LEN='):
                    buf_len = l.split('=')[1]
                if 'memo=prompt-footer' in l:
                    print(f"  {l}")
            print(f"  BUFFER_LEN={buf_len} own_entries={count_own_rh_entries(content)}")

        # ---- SCENARIO 3: After accept ----
        print("\n=== SCENARIO 3: After accept (new prompt entries shown) ===")
        os.write(fd, b'\n')
        time.sleep(0.4); read_all(fd, 0.3)

        content = probe_state(fd, probe_file)
        if content:
            count = count_own_rh_entries(content)
            print(f"own_entries={count} (for new empty-buffer prompt)")
            for l in content.split('\n'):
                if 'memo=prompt-footer' in l:
                    print(f"  {l}")

        # ---- SCENARIO 4: Different prefix lengths ----
        print("\n=== SCENARIO 4: Varying prefix length ===")
        for prefix in ['echo 1', 'echo 12345', 'echo ' + 'x' * 20]:
            os.write(fd, f'{prefix}\n'.encode())
            time.sleep(0.4); read_all(fd, 0.2)
            time.sleep(0.3)

            content = probe_state(fd, probe_file)
            if content:
                buf_len = None
                own = count_own_rh_entries(content)
                for l in content.split('\n'):
                    if l.startswith('BUFFER_LEN='):
                        buf_len = l.split('=')[1]
                print(f"Prefix {prefix!r}: BUFFER_LEN={buf_len} own_entries={own}")
                for l in content.split('\n'):
                    if 'memo=prompt-footer' in l:
                        print(f"  {l}")

        # ---- SCENARIO 5: Ctrl+L clear ----
        print("\n=== SCENARIO 5: Ctrl+L after accept ===")
        os.write(fd, b'echo test\n')
        time.sleep(0.3); read_all(fd, 0.2)
        os.write(fd, b'\x0c')  # Ctrl+L
        time.sleep(0.4); read_all(fd, 0.2)

        content = probe_state(fd, probe_file)
        if content:
            own = count_own_rh_entries(content)
            print(f"own_entries={own}")
            for l in content.split('\n'):
                if 'memo=prompt-footer' in l:
                    print(f"  {l}")

        print("\nDone.")
    finally:
        os.write(fd, b'exit\n')
        time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)
        try: os.unlink(probe_file)
        except: pass
        shutil.rmtree(dirty_repo, ignore_errors=True)

if __name__ == '__main__':
    run()
