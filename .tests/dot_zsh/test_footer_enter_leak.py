#!/usr/bin/env python3
"""
RED test: after Enter, the previous prompt's footer must NOT appear between
the command line and its output.
"""
import os, sys, pty, select, time, re

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(TEST_DIR, '.venv', 'lib',
    f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages'))

def spawn():
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '24'
        probe_dir = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(probe_dir, exist_ok=True)
        # Use REAL zsh config so autosuggestions are loaded
        with open(os.path.join(probe_dir, '.zshrc'), 'w') as f:
            f.write('source ~/.zshrc 2>/dev/null || true\n')
        with open(os.path.join(probe_dir, '.zshenv'), 'w') as f:
            f.write('export ZDOTDIR="$HOME"\n')
        os.environ['ZDOTDIR'] = probe_dir
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)
    return pid, fd

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
    """Split on actual \\n only (not \\r which is used for same-line redraws)."""
    text = raw.decode('utf-8', errors='replace')
    lines = text.replace('\r\n', '\n').split('\n')
    # Within each line, multiple \r-separated segments are same-position redraws.
    # Only keep the LAST segment after each \r (the final visible state on that line).
    result = []
    for l in lines:
        # \r moves cursor to beginning; the last segment after the final \r wins
        segments = l.split('\r')
        final = strip_ansi(segments[-1])
        if final:
            result.append(final)
    return result

def find_footer_leak(raw):
    visible = visible_lines(raw)
    cmd_idx = -1
    for i, s in enumerate(visible):
        if 'echo hello' in s:
            cmd_idx = i
            break
    if cmd_idx < 0:
        return None, "cmd not found"
    out_idx = -1
    for i in range(cmd_idx + 1, len(visible)):
        if visible[i] in ('hello world', 'hello', 'h'):
            out_idx = i
            break
    for i in range(cmd_idx + 1, len(visible) if out_idx < 0 else out_idx):
        s = visible[i]
        if s.startswith('~') or s.startswith('/') or 'zsh' in s:
            return True, f"footer in-between: {repr(s)}"
    if out_idx < 0:
        return None, "output not found"
    return False, None

def run_test(name, cmd, post_type_cmd=''):
    pid, fd = spawn()
    time.sleep(1.0)
    read_all(fd, 0.5)
    if post_type_cmd:
        os.write(fd, post_type_cmd.encode())
        time.sleep(1.8)
        read_all(fd, 0.3)
    os.write(fd, (cmd + '\n').encode())
    time.sleep(0.8)
    raw = read_all(fd, 0.5)
    leaked, msg = find_footer_leak(raw)
    if leaked:
        print(f'  FAIL: {name} — {msg}')
        for v in visible_lines(raw):
            print(f'    vis: {repr(v)}')
    else:
        print(f'  PASS: {name}')
    os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)
    return not leaked

def run_test2():
    """Type partial command, ghost text appears, then press Enter. Check no footer leak."""
    pid, fd = spawn()
    time.sleep(1.0)
    read_all(fd, 0.5)
    # Type partial command that triggers a suggestion
    os.write(fd, b'echo h')
    time.sleep(1.5)
    read_all(fd, 0.3)
    # Press Enter on the partial command (NOT accept suggestion)
    os.write(fd, b'\n')
    time.sleep(0.8)
    raw = read_all(fd, 0.5)
    vis = visible_lines(raw)
    print("Visible lines after Enter on 'echo h':")
    for v in vis:
        print(f"  {repr(v)}")
    # Check: after 'echo h' is accepted, the output should be 'h'
    # The sequence should be: prompt line -> output 'h' -> next prompt -> footer
    # Count footer lines (starting with ~ or / and containing path)
    footer_lines = [v for v in vis if v.startswith('~') or (v.startswith('/') and len(v) > 3)]
    if len(footer_lines) > 1:
        print(f"  [FAIL] {len(footer_lines)} footer lines found (expected 1)")
        return False
    elif len(footer_lines) == 0:
        print("  [FAIL] No footer found")
        return False
    else:
        print(f"  [PASS] 1 footer line")
        return True

ok = run_test2()
print()
print(f"{'[PASS]' if ok else '[FAIL]'} No footer leak on Enter with ghost text")
sys.exit(0 if ok else 1)
