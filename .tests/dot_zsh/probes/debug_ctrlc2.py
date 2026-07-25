#!/usr/bin/env python3
"""Debug ctrl+c test - print raw terminal output."""
import os, sys, pty, select, time, glob, shutil, re

TEST_DIR = '/Users/lvl2pillow/.local/share/chezmoi/.tests/dot_zsh'
PROBE_PATH = os.path.join(TEST_DIR, 'test_probe_ctrlc_bug.zsh')

def spawn():
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '24'
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

def strip_escapes(text):
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)

for d in glob.glob('/tmp/zsh_probe_*'):
    shutil.rmtree(d, ignore_errors=True)

pid, fd = spawn()
wait_for_output(fd, min_bytes=30, max_wait=2.0)
read_all(fd, 0.3)

# Type command
os.write(fd, b'sleep 5 && echo 1')
time.sleep(0.3)
read_all(fd, 0.3)

# Ctrl+C #1
os.write(fd, b'\x03')
time.sleep(0.4)
c1 = read_all(fd, 0.4)
print(f"=== AFTER CTRL+C #1 (non-empty buffer) ({len(c1)} bytes) ===")
t1 = strip_escapes(c1.decode('utf-8', errors='replace'))
for i, line in enumerate(t1.replace('\r\n', '\n').replace('\r', '\n').split('\n')):
    print(f"  {i}: {line!r}")

# Ctrl+C #2
os.write(fd, b'\x03')
time.sleep(0.6)
c2 = read_all(fd, 0.6)
print(f"\n=== AFTER CTRL+C #2 (empty buffer) ({len(c2)} bytes) ===")
t2 = strip_escapes(c2.decode('utf-8', errors='replace'))
for i, line in enumerate(t2.replace('\r\n', '\n').replace('\r', '\n').split('\n')):
    print(f"  {i}: {line!r}")

# Combined
combined = c1 + c2
total = strip_escapes(combined.decode('utf-8', errors='replace'))
print(f"\n=== TOTAL >> COUNT: {total.count('>>')} ===")

os.write(fd, b'exit\n')
time.sleep(0.3)
os.close(fd)
os.waitpid(pid, 0)
