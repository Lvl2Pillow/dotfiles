#!/usr/bin/env python3
"""Debug: print raw output around Ctrl+C events."""
import os, sys, pty, select, time, glob, shutil

# Hardcode test dir path
TEST_DIR = '/Users/lvl2pillow/.local/share/chezmoi/.tests/dot_zsh'
PROBE_PATH = os.path.join(TEST_DIR, 'test_prompt_probe.zsh')


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
        if not r:
            break
        try:
            chunk = os.read(fd, 8192)
            if not chunk:
                break
            out += chunk
        except OSError:
            break
    return out


def wait_for_output(fd, min_bytes=10, max_wait=3.0):
    out = b''
    deadline = time.time() + max_wait
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.3)
        if r:
            try:
                chunk = os.read(fd, 8192)
                if not chunk:
                    break
                out += chunk
                if len(out) >= min_bytes:
                    break
            except OSError:
                break
    return out


def cleanup():
    for d in glob.glob('/tmp/zsh_probe_*'):
        shutil.rmtree(d, ignore_errors=True)


cleanup()
pid, fd = spawn()

init = wait_for_output(fd, min_bytes=50, max_wait=4.0)
print(f"INITIAL ({len(init)} bytes)")
if init:
    # Show text without escape codes
    import re
    noesc = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', init.decode('utf-8', errors='replace'))
    print(repr(noesc[:300]))
else:
    print("EMPTY")
    try:
        os.kill(pid, 0)
        print("zsh alive")
    except:
        print("zsh died")

# Type a command
os.write(fd, b'sleep 5 && echo 1')
time.sleep(0.3)
t = read_all(fd, 0.3)
print(f"\nTYPED ({len(t)} bytes)")
if t:
    noesc = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', t.decode('utf-8', errors='replace'))
    print(repr(noesc[:200]))

# Ctrl+C #1 (non-empty buffer)
os.write(fd, b'\x03')
time.sleep(0.4)
c1 = read_all(fd, 0.4)
print(f"\nCTRL+C #1 ({len(c1)} bytes)")
if c1:
    noesc = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', c1.decode('utf-8', errors='replace'))
    print(repr(noesc[:300]))

# Ctrl+C #2 (empty buffer)
os.write(fd, b'\x03')
time.sleep(0.6)
c2 = read_all(fd, 0.6)
print(f"\nCTRL+C #2 ({len(c2)} bytes)")
if c2:
    noesc = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', c2.decode('utf-8', errors='replace'))
    print(repr(noesc[:500]))

print("\n=== ALL TEXT ===")
all_data = init + t + c1 + c2
noesc = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', all_data.decode('utf-8', errors='replace'))
for i, line in enumerate(noesc.replace('\r\n', '\n').replace('\r', '\n').split('\n')):
    print(f"{i:3d}: {line!r}")

try:
    os.write(fd, b'exit\n')
    time.sleep(0.3)
    os.close(fd)
    os.waitpid(pid, 0)
except:
    pass
cleanup()
