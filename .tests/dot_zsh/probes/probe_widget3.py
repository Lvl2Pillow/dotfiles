import os, pty, select, time, re

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

# Log EVERYTHING — patch all entry points that might append footer
config = r'''
source ~/.zshrc 2>/dev/null || true

echo "WIDGET_LOGGING_ACTIVE" >&2

# Patch zle widget hooks to log when they run
typeset -ag _prompt_widget_log=()

# Overwrite _prompt_zle_append_footer entirely to log
_prompt_zle_append_footer() {
  emulate -L zsh
  local stack
  stack="${funcfiletrace[1]}"
  _prompt_widget_log+=("FUNC WIDGET=[$WIDGET] stack=$stack")
  [[ -z "$_prompt" ]] && { _prompt_widget_log+=("  skip: no _prompt"); return 0; }
  zle 2>/dev/null && ZLE_VAL=Y || ZLE_VAL=N
  _prompt_widget_log+=("  zle=$ZLE_VAL")
  if [[ $ZLE_VAL = N ]]; then
    _prompt_widget_log+=("  skip: not in ZLE"); return 0
  fi
  if [[ $WIDGET = *accept-line* ]]; then
    _prompt_widget_log+=("  skip: accept-line"); return 0
  fi
  _prompt_widget_log+=("  WOULD_APPEND")
  return 0
}
echo "PATCH_ACTIVE" >&2
'''

import subprocess
subprocess.run(['rm', '-f', '/tmp/widget6.log'], capture_output=True)

import os, pty, select, time
pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
    d = f'/tmp/zsh_probe6_{os.getpid()}'; os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config + '\n')
    os.environ['ZDOTDIR'] = d
    os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)

time.sleep(1.5); read_all(fd, 0.3)
os.write(fd, b'echo ok\n'); time.sleep(0.5)
read_all(fd, 0.3)

# Log to stderr to ensure we get all output in PTY
os.write(fd, b'typeset -p _prompt_widget_log 2>&1\n'); time.sleep(0.5)
raw = read_all(fd, 0.5)
text = raw.decode('utf-8', errors='replace')
for line in text.split('\n'):
    if 'widge' in line.lower() or 'PATCH' in line or 'LOG' in line:
        print(repr(line))
os.close(fd); os.waitpid(pid, 0)
