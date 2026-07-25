import os, pty, select, time, re

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

# Log to file, patch _prompt_zle_append_footer 
config = r'''
source ~/.zshrc 2>/dev/null || true

_prompt_zle_append_footer() {
  emulate -L zsh
  {
    zle 2>/dev/null && ZLEV=Y || ZLEV=N
    echo "WIDGET=[$WIDGET] ZLE=$ZLEV BUFFER_LEN=${#BUFFER}" >> /tmp/widget_log.$$
    [[ -z "$_prompt" ]] && { echo "SKIP_NOPROMPT" >> /tmp/widget_log.$$; return 0; }
    if [[ $ZLEV = N ]]; then echo "SKIP_NO_ZLE" >> /tmp/widget_log.$$; return 0; fi
    if [[ $WIDGET = *accept-line* ]]; then echo "SKIP_ACCEPT" >> /tmp/widget_log.$$; return 0; fi
    echo "APPEND" >> /tmp/widget_log.$$
  } 2>/dev/null
  return 0
}
echo "PATCH_DONE" >&2
'''

import glob
for f in glob.glob('/tmp/widget_log.*'): os.unlink(f)

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
    d = f'/tmp/zsh_probe7_{os.getpid()}'; os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config + '\n')
    os.environ['ZDOTDIR'] = d
    os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)

time.sleep(1.5); read_all(fd, 0.3)
os.write(fd, b'\n'); time.sleep(0.5)
read_all(fd, 0.3)

for log in sorted(glob.glob('/tmp/widget_log.*')):
    with open(log) as f:
        print(f.read())
    os.unlink(log)
os.close(fd); os.waitpid(pid, 0)
