#!/usr/bin/env python3
"""After 2 commands, old footer from cmd1 must not persist."""
import os, pty, select, time, re

def read_all(fd, t=0.5):
    out=b''
    while True:
        r,_,_=select.select([fd],[],[],t)
        if not r: break
        try:
            c=os.read(fd,8192)
            if not c: break
            out+=c
        except: break
    return out

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM']='xterm-256color'; os.environ['COLUMNS']='80'; os.environ['LINES']='24'
    os.execvpe('zsh',['zsh','-i'],os.environ); os._exit(1)

time.sleep(0.8); read_all(fd, 0.5)

# Command 1
os.write(fd, b'echo one\n')
time.sleep(0.6)
read_all(fd, 0.3)

# Command 2
os.write(fd, b'echo two\n')
time.sleep(0.6)
raw = read_all(fd, 0.5)

text = raw.decode('utf-8', errors='replace')
lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')

print("=== After echo two (cmd2) ===")
for i, l in enumerate(lines):
    clean = l.replace('\x1b', 'ESC')
    print(f"{i:2d}: {repr(clean)[:120]}")

# Count footer lines — look for dir/branch after the prompt %, not in OSC 7 sequences
# OSC 7 contains file://... as encoded path, not plain ~/.zsh
import re
# Footer lines have bold+color THEN ~/.zsh
# Strip escape sequences
stripped_lines = []
for l in lines:
    s = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', l)
    s = re.sub(r'\x1b\][^\x07]*\x07', '', s)
    stripped_lines.append(s.strip())

print("\n=== Stripped lines ===")
for i, s in enumerate(stripped_lines):
    if s:
        print(f"{i:2d}: {repr(s)}")

footer_lines = [s for s in stripped_lines if s.startswith('~') or s.startswith('/')]
print(f"\nFooter lines (dir/branch content): {len(footer_lines)}")
if len(footer_lines) > 1:
    print(f"[FAIL] Multiple footers: {footer_lines}")
else:
    print("[PASS] Single footer visible")

os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)
