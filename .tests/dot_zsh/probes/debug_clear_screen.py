#!/usr/bin/env python3
"""Check if zle -R -c sends clear-screen escape in output."""
import os, sys, pty, select, time, glob, shutil

TEST_DIR = '/Users/lvl2pillow/.local/share/chezmoi/.tests/dot_zsh'
PROBE_PATH = os.path.join(TEST_DIR, 'test_probe_ctrlc_bug.zsh')

def spawn():
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '10'
        os.environ['TERM_PROGRAM'] = ''
        probe_dir = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(probe_dir, exist_ok=True)
        with open(os.path.join(probe_dir, '.zshrc'), 'w') as f:
            with open(PROBE_PATH) as src:
                f.write(src.read())
        with open(os.path.join(probe_dir, '.zshenv'), 'w') as f:
            f.write('# empty\n')
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
            chunk = os.read(fd, 8192)
            if not chunk: break
            out += chunk
        except OSError: break
    return out

def wait_for_output(fd, min_bytes=10, max_wait=4.0):
    out = b''
    deadline = time.time() + max_wait
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.3)
        if r:
            try:
                chunk = os.read(fd, 8192)
                if not chunk: break
                out += chunk
                if len(out) >= min_bytes: break
            except OSError: break
    return out

for d in glob.glob('/tmp/zsh_probe_*'):
    shutil.rmtree(d, ignore_errors=True)

pid, fd = spawn()
wait_for_output(fd, min_bytes=30, max_wait=2.0)
read_all(fd, 0.3)

# Type a command, then two Ctrl+C
os.write(fd, b'sleep 5 && echo 1')
time.sleep(0.3)
read_all(fd, 0.3)

os.write(fd, b'\x03')  # ctrl+c #1
time.sleep(0.4)
c1 = read_all(fd, 0.4)

os.write(fd, b'\x03')  # ctrl+c #2 (empty buffer)
time.sleep(0.6)
c2 = read_all(fd, 0.6)

print("=== C2 raw bytes ===")
print(repr(c2))
print()

# Check for clear-screen escape
if b'\x1b[H\x1b[2J' in c2:
    print("FOUND: clear-screen escape \\x1b[H\\x1b[2J")
elif b'\x1b[2J' in c2:
    print("FOUND: \\x1b[2J (clear display)")
elif b'\x1b[1;1H' in c2:
    print("FOUND: cursor home")
else:
    print("NO clear-screen escape found in c2")
    print(f"Escape sequences present:")
    import re
    for m in re.finditer(rb'\x1b\[[0-9;]*[a-zA-Z]', c2):
        print(f"  {m.group()!r}")

os.write(fd, b'exit\n')
time.sleep(0.3)
os.close(fd)
os.waitpid(pid, 0)
cleanup()
