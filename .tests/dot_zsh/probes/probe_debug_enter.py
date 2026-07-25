#!/usr/bin/env python3
"""Debug: count calls to _prompt_zle_append_footer and check WIDGET."""
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

# Inject debug into _prompt_zle_append_footer by redefining it
debug = b'''
_prompt_af_counter=${_prompt_af_counter:-0}
typeset -a _prompt_af_widgets
_prompt_zle_append_footer() {
  emulate -L zsh
  _prompt_af_counter=$(( _prompt_af_counter + 1 ))
  _prompt_af_widgets+=("$WIDGET")
  [[ -z "$_prompt" ]] && return 0
  [[ $WIDGET = *accept-line* ]] && return 0
  ...rest...
}
'''
# Actually let me just check what functions are wrapping accept-line
os.write(fd, b'zle -la | grep -i accept | head -5\n')
time.sleep(0.3); read_all(fd, 0.2)

# Check the widget that wraps accept-line
os.write(fd, b'echo "WIDGETS:"; zle -la accept\n')
time.sleep(0.3); read_all(fd, 0.2)

# Type echo h with ghost then Enter
os.write(fd, b'echo h')
time.sleep(1.5); read_all(fd, 0.3)
os.write(fd, b'\n')
time.sleep(0.8)
raw = read_all(fd, 0.5)

text = raw.decode('utf-8', errors='replace').replace('\r\n','\n').replace('\r','\n')
print("Raw lines after Enter:")
for i, l in enumerate(text.split('\n')[:15]):
    clean = l.replace('\x1b', 'ESC')
    print(f"{i}: {repr(clean)[:120]}")

os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)
