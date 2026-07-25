#!/usr/bin/env python3
"""Probe if _prompt_rh_entries is empty when it shouldn't be."""
import os, pty, select, time, re

def read_all(fd, t=0.5):
    out = b''
    while True:
        r,_,_ = select.select([fd],[],[],t)
        if not r: break
        try:
            c = os.read(fd,8192)
            if not c: break
            out += c
        except: break
    return out

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM']='xterm-256color'; os.environ['COLUMNS']='80'; os.environ['LINES']='24'
    os.execvpe('zsh',['zsh','-i'],os.environ); os._exit(1)

time.sleep(0.8); read_all(fd,0.5)

# Define a widget that dumps region_highlight to a temp file
# This way we can read it after zle finishes
setup = b'''
_prompt_debug_rh() {
  local f=/tmp/_rh_dump_$$
  print -r -- "BUFFER=$#BUFFER POSTDISPLAY=$#POSTDISPLAY _prompt_len=$#_prompt _prompt_dir_len=$_prompt_dir_len" > "$f"
  print -r -- "RH: ${region_highlight[*]}" >> "$f"
  print -r -- "PRE: ${_prompt_rh_entries[*]}" >> "$f"
  print -r -- "_prompt=$_prompt" >> "$f"
  zle -M "dumped to $f"
  zle -R
}
zle -N _prompt_debug_rh
bindkey '^T' _prompt_debug_rh
'''
# Type setup commands one at a time
os.write(fd, setup)
time.sleep(0.2)
os.write(fd, b'\n')  # execute setup
time.sleep(0.5)
read_all(fd, 0.3)

os.write(fd, b'echo hello world\n')
time.sleep(0.5)
read_all(fd, 0.3)

os.write(fd, b'echo h')
time.sleep(1.5)
read_all(fd, 0.3)

# Press Ctrl+T to dump state BEFORE accept
os.write(fd, b'\x14')  # Ctrl+T
time.sleep(0.3)
read_all(fd, 0.2)
# Read the dump
import subprocess
r = subprocess.run(['cat', '/tmp/_rh_dump_40814'], capture_output=True, text=True, timeout=2)
print("BEFORE accept:")
print(r.stdout)

# Now accept
os.write(fd, b'\x06')  # Ctrl+F to accept
time.sleep(0.5)
read_all(fd, 0.3)

# Press Ctrl+T AGAIN to dump AFTER accept
os.write(fd, b'\x14')
time.sleep(0.3)
read_all(fd, 0.2)
r2 = subprocess.run(['cat', '/tmp/_rh_dump_40814'], capture_output=True, text=True, timeout=2)
print("AFTER accept:")
print(r2.stdout)

os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid,0)
