#!/usr/bin/env python3
"""
RED test: with real zsh config + autosuggestions, pressing Enter must not
leave the previous prompt's footer visible between command line and output.
"""
import os, pty, select, time, re

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM']='xterm-256color'; os.environ['COLUMNS']='80'; os.environ['LINES']='24'
    os.execvpe('zsh',['zsh','-i'],os.environ); os._exit(1)

time.sleep(0.8);
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

read_all(fd, 0.5)

# Type a command. Its prompt will have a POSTDISPLAY footer.
# Press Enter. Check that the OLD footer does NOT appear between cmd line and output.
os.write(fd, b'echo hello world\n')
time.sleep(0.8)
raw = read_all(fd, 0.5)

text = raw.decode('utf-8', errors='replace')
lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')

print("=== After Enter (with real config) ===")
for i, l in enumerate(lines):
    clean = l.replace('\x1b', 'ESC')
    print(f"{i:2d}: {repr(clean)[:120]}")

# The expected output:
#   % echo hello world   (or similar prompt)
#   (empty line between prompt and output - just \n from accept-line)
#   hello world          (command output)
#   % ~/.zsh main        (new prompt + footer)
#
# BUG: old footer appears between command line and output:
#   % echo hello world
#   ~/.zsh main          ← BUG: old footer leaked!
#   hello world
#   % ~/.zsh main

# Check: look for any non-empty line between the command line and "hello world"
# that looks like a footer (has dir/git content)
out_lines = []
for l in lines:
    s = l.strip()
    if s and s not in ('%') and 'echo hello world' not in s and 'hello world' not in s:
        out_lines.append(s)
        
print(f"\nNon-standard lines: {out_lines}")

# Specifically check for directory-like content between echo and hello
between_cmd_and_out = []
found_cmd = False
for l in lines:
    if 'echo hello world' in l:
        found_cmd = True
    elif 'hello world' in l.strip():
        break
    elif found_cmd and l.strip():
        between_cmd_and_out.append(l.strip())

if between_cmd_and_out:
    print(f"\n[FAIL] Content between command and output: {between_cmd_and_out}")
    print("  (Previous footer likely leaking!)")
else:
    print("\n[PASS] No content between command line and output")

os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)
