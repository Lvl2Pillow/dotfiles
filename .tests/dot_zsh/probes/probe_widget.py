import os, pty, select, time

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

# Patch _prompt_zle_append_footer to log every call
_prompt_zle_append_footer_tmp() {
  emulate -L zsh
  echo "CALL:WIDGET=[$WIDGET] ZLE=$(zle 2>/dev/null && echo Y || echo N)" >> /tmp/widget4.log
  [[ -z "$_prompt" ]] && { echo "  skip: no _prompt" >> /tmp/widget4.log; return 0; }
  if ! zle 2>/dev/null; then
    echo "  skip: not in ZLE" >> /tmp/widget4.log; return 0
  fi
  if [[ $WIDGET = *accept-line* ]]; then
    echo "  skip: accept-line WIDGET" >> /tmp/widget4.log; return 0
  fi
  echo "  WOULD_APPEND" >> /tmp/widget4.log
  return 0
}
functions[_prompt_zle_append_footer]=$functions[_prompt_zle_append_footer_tmp]
echo PATCH_DONE >&2
'''

import subprocess
subprocess.run(['rm', '-f', '/tmp/widget4.log'], capture_output=True)

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
    d = f'/tmp/zsh_probe4_{os.getpid()}'; os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config + '\n')
    os.environ['ZDOTDIR'] = d
    os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)

time.sleep(1.5); read_all(fd, 0.3)
os.write(fd, b'\n'); time.sleep(0.5)
read_all(fd, 0.3)

with open('/tmp/widget4.log') as f:
    print(f.read())
os.close(fd); os.waitpid(pid, 0)
