#!/usr/bin/env python3
"""Probe exact WIDGET value during footer append on Enter with ghost."""
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
    probe_dir = f'/tmp/zsh_probe_{os.getpid()}'
    os.makedirs(probe_dir, exist_ok=True)
    with open(os.path.join(probe_dir, '.zshrc'), 'w') as f:
        f.write('''source ~/.zshrc 2>/dev/null || true
# Override with debug that logs WIDGET to a file
_zsh_autosuggest_highlight_apply() {
  local w="$WIDGET"
  _zsh_autosuggest_highlight_apply_orig "$@"
  {
    echo "WIDGET=$w FOOTER_BEFORE=${POSTDISPLAY:+YES} FOOTER_IN_POSTDISPLAY=$([[ "$POSTDISPLAY" = *$_prompt ]] && echo YES || echo no)"
  } >> /tmp/_prompt_debug_$$
  _prompt_zle_append_footer
}
''')
    with open(os.path.join(probe_dir, '.zshenv'), 'w') as f:
        f.write('# empty\n')
    os.environ['ZDOTDIR'] = probe_dir
    os.execvpe('zsh', ['zsh', '-i'], os.environ)
    os._exit(1)

time.sleep(0.8); read_all(fd, 0.5)

# Type partial command with ghost
os.write(fd, b'echo h')
time.sleep(1.5); read_all(fd, 0.3)

# Get PID for debug file
os.write(fd, b'echo "MY_PID=$$"\n')
time.sleep(0.3)
out = read_all(fd, 0.2)
import subprocess
pid_match = re.search(rb'MY_PID=(\d+)', out)
if pid_match:
    zsh_pid = pid_match.group(1).decode()
    print(f"Zsh PID: {zsh_pid}")
    debug_file = f'/tmp/_prompt_debug_{zsh_pid}'
else:
    print("Could not find PID")
    debug_file = '/tmp/_prompt_debug_*'

time.sleep(0.5)  # let any pending reads clear

# Clear debug file
subprocess.run(['bash', '-c', f'[ -f {debug_file} ] && cp /dev/null {debug_file} || true'], timeout=2)

# Now press Enter
os.write(fd, b'\n')
time.sleep(0.8)
read_all(fd, 0.5)

# Read debug file
try:
    r2 = subprocess.run(['cat', debug_file], capture_output=True, text=True, timeout=2)
    print("Debug output from footer_append:")
    for l in r2.stdout.strip().split('\n'):
        print(f"  {l}")
except Exception as e:
    print(f"Error reading debug file: {e}")

os.write(fd, b'\n'); time.sleep(0.2)  # just enter to get new prompt
os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)
