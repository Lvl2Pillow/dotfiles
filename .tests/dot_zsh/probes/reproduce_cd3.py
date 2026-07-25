#!/usr/bin/env python3
"""Test cd with quoted $(chezmoi source-path) and check for errors."""
import os, pty, select, time

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

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'
    os.environ['LINES'] = '24'
    os.environ['TERM_PROGRAM'] = ''
    os.execvpe('zsh', ['zsh', '-i'], os.environ)
    os._exit(1)

time.sleep(0.8)
read_all(fd, 0.5)
read_all(fd, 0.3)

# First cd somewhere to trigger pwd change
os.write(fd, b'cd ~/.local/share/chezmoi\n')
time.sleep(0.5)
read_all(fd, 0.3)

# Now do the exact command: cd "$(chezmoi source-path)"
os.write(fd, b'cd "$(chezmoi source-path)"\n')
time.sleep(1.0)
out = read_all(fd, 0.5)

text = out.decode('utf-8', errors='replace')
print(f"Output ({len(out)} bytes):")
print(repr(text[-500:]))
if 'permission' in text.lower():
    print("*** PERMISSION DENIED FOUND ***")
    import re
    for m in re.finditer(r'[^\n]*permission[^\n]*', text, re.I):
        print(f"  Error: {m.group()}")

os.write(fd, b'pwd\n')
time.sleep(0.3)
out2 = read_all(fd, 0.3)
print(f"pwd: {out2.decode('utf-8', errors='replace')[:100]}")

os.write(fd, b'exit\n')
time.sleep(0.2)
os.close(fd)
os.waitpid(pid, 0)
