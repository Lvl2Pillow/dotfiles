#!/usr/bin/env python3
"""Debug: raw PTY output after Enter with real config."""
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

# Press Enter on a simple command
os.write(fd, b'echo hello\n')
time.sleep(0.8)
raw = read_all(fd, 0.5)

text = raw.decode('utf-8', errors='replace')
lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')

print("=== Raw after Enter with real config ===")
for i, l in enumerate(lines):
    clean = l.replace('\x1b', 'ESC')
    print(f"{i:2d}: {repr(clean)[:140]}")

# Strip all escape sequences
print("\n=== Stripped ===")
for i, l in enumerate(lines):
    s = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', l)
    s = re.sub(r'\x1b\][^\x07]*\x07', '', s)
    s = s.strip()
    if s:
        print(f"{i:2d}: {repr(s)[:100]}")

os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)
