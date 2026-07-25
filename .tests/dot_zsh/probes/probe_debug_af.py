#!/usr/bin/env python3
"""Add debug counter to _prompt_zle_append_footer to trace calls."""
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
    # Use custom .zshrc that adds debugging
    probe_dir = f'/tmp/zsh_probe_{os.getpid()}'
    os.makedirs(probe_dir, exist_ok=True)
    # Write a custom .zshrc with debug
    with open(os.path.join(probe_dir, '.zshrc'), 'w') as f:
        f.write('''source ~/.zshrc 2>/dev/null || true
typeset -a _prompt_dbg_widgets
typeset -a _prompt_dbg_calls
typeset -i _prompt_dbg_skip=0
typeset -i _prompt_dbg_noskip=0
# Override the function with debug
_zsh_autosuggest_highlight_apply() {
  local w="$WIDGET"
  _zsh_autosuggest_highlight_apply_orig "$@"
  _prompt_rh_calls=$(( _prompt_rh_calls + 1 ))
  _prompt_rh_widgets+=("$w")
  if [[ $w = *accept-line* ]]; then
    _prompt_dbg_skip=$(( _prompt_dbg_skip + 1 ))
  else
    _prompt_dbg_noskip=$(( _prompt_dbg_noskip + 1 ))
  fi
  _prompt_zle_append_footer
}
''')
    with open(os.path.join(probe_dir, '.zshenv'), 'w') as f:
        f.write('# empty\\n')
    os.environ['ZDOTDIR'] = probe_dir
    os.execvpe('zsh', ['zsh', '-i'], os.environ)
    os._exit(1)

time.sleep(0.8); read_all(fd, 0.5)

# Type partial command and press Enter
os.write(fd, b'echo h')
time.sleep(1.5); read_all(fd, 0.3)
os.write(fd, b'\n')
time.sleep(0.8)
raw = read_all(fd, 0.5)

# Read debug vars
os.write(fd, b'echo "calls=$_prompt_rh_calls skip=$_prompt_dbg_skip noskip=$_prompt_dbg_noskip"\n')
time.sleep(0.3)
out = read_all(fd, 0.3)
t = out.decode(errors='replace')
t = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]','',t)
t = re.sub(r'\x1b\][^\x07]*\x07','',t)
print("Debug:", t.split('calls=')[-1].split('\n')[0] if 'calls=' in t else t[:200])

os.write(fd, b'echo "widgets: ${_prompt_rh_widgets[*]}"\n')
time.sleep(0.3)
out2 = read_all(fd, 0.3)
t2 = out2.decode(errors='replace')
t2 = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]','',t2)
t2 = re.sub(r'\x1b\][^\x07]*\x07','',t2)
print("Widgets:", t2.split('widgets:')[-1].split('\n')[0] if 'widgets:' in t2 else t2[:200])

os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)
