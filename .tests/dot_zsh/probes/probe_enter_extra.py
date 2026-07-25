#!/usr/bin/env python3
"""Check if there's an extra blank line or footer ghost after Enter."""
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

# Use a distinct marker as the command so we can track lines
os.write(fd, b'echo ZYXWVU\n')
time.sleep(0.8)
raw = read_all(fd, 0.5)

text = raw.decode('utf-8', errors='replace').encode('utf-8').decode('utf-8', errors='replace')
lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')

print("=== After Enter (looking for stray footer) ===")
for i, l in enumerate(lines):
    clean = l.replace('\x1b', 'ESC')
    # Check for any line that has path-like content (footer)
    has_path = bool(re.search(r'[/~]\w', l))
    print(f"{i:2d} [{'!' if has_path else ' '}]: {repr(clean)[:120]}")

# Check specifically for the bug: is there a ~/.zsh line between ZYXWVU (output) and % (next prompt)?
stripped = []
for l in lines:
    s = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', l)
    s = re.sub(r'\x1b\][^\x07]*\x07', '', s)
    s = s.strip()
    stripped.append(s)

print("\n=== Sequence analysis ===")
# Find ZYXWVU (command output)
out_idx = -1
prompt_idx = -1
for i, s in enumerate(stripped):
    if 'ZYXWVU' in s:
        out_idx = i
    if s == '%' and out_idx >= 0 and prompt_idx < 0:
        prompt_idx = i

if out_idx >= 0 and prompt_idx >= 0:
    between = stripped[out_idx+1:prompt_idx]
    print(f"Lines between output and next prompt: {between}")
    if between:
        print("[FAIL] Extra content between output and next prompt!")
        for s in between:
            if s.startswith('~') or s.startswith('/') or 'zsh' in s:
                print(f"  -> Footer content: {repr(s)}")
    else:
        print("[PASS] No extra content between output and prompt")
else:
    print(f"out_idx={out_idx}, prompt_idx={prompt_idx}")

os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)
