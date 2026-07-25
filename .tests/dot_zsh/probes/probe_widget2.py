import os, pty, select, time, re

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

config = r'''
source ~/.zshrc 2>/dev/null || true

# Step 1: Check if zle works in function body (not in subshell)
_prompt_zle_append_footer_tmp() {
  emulate -L zsh
  zle 2>/dev/null && ZLE_VAL=Y || ZLE_VAL=N
  echo "CALL:WIDGET=[$WIDGET] ZLE=$ZLE_VAL" >> /tmp/widget5.log
  [[ -z "$_prompt" ]] && { echo "  skip: no _prompt" >> /tmp/widget5.log; return 0; }
  if [[ $ZLE_VAL = N ]]; then
    echo "  skip: not in ZLE" >> /tmp/widget5.log; return 0
  fi
  [[ $WIDGET = *accept-line* ]] && { echo "  skip: accept-line WIDGET[$WIDGET]" >> /tmp/widget5.log; return 0; }
  echo "  WOULD_APPEND" >> /tmp/widget5.log
  return 0
}
functions[_prompt_zle_append_footer]=$functions[_prompt_zle_append_footer_tmp]
echo PATCH_DONE >&2
'''

import subprocess
subprocess.run(['rm', '-f', '/tmp/widget5.log'], capture_output=True)

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
    d = f'/tmp/zsh_probe5_{os.getpid()}'; os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config + '\n')
    os.environ['ZDOTDIR'] = d
    os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)

time.sleep(1.5); read_all(fd, 0.3)
os.write(fd, b'\n'); time.sleep(0.5)
read_all(fd, 0.3)

with open('/tmp/widget5.log') as f:
    print(f.read())
os.close(fd); os.waitpid(pid, 0)
