import os, pty, select, time, glob

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

# Log eval context inside _prompt_zle_append_footer
_prompt_zle_append_footer() {
  emulate -L zsh
  echo "CTX=[$ZSH_EVAL_CONTEXT] WIDGET=[$WIDGET]" >> /tmp/ctx_log.$$
  [[ -z "$_prompt" ]] && return 0
  zle 2>/dev/null && ZV=Y || ZV=N
  echo "ZLE=$ZV" >> /tmp/ctx_log.$$
  [[ $ZV = N ]] && return 0
  [[ $WIDGET = *accept-line* ]] && return 0
  local ghost="${POSTDISPLAY%%$'\n'*}" 2>>/tmp/ctx_err.$$
  POSTDISPLAY="${ghost}"$'\n'"${_prompt}" 2>>/tmp/ctx_err.$$
  echo "DONE" >> /tmp/ctx_log.$$
  return 0
}
echo "PATCH_DONE" >&2
'''

for f in glob.glob('/tmp/ctx_log.*'): os.unlink(f)
for f in glob.glob('/tmp/ctx_err.*'): os.unlink(f)

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
    d = f'/tmp/zsh_probe_{os.getpid()}'; os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config + '\n')
    os.environ['ZDOTDIR'] = d
    os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)

time.sleep(1.5); read_all(fd, 0.3)
os.write(fd, b'\n'); time.sleep(0.5); read_all(fd, 0.3)

for log in sorted(glob.glob('/tmp/ctx_log.*')):
    with open(log) as f: print(f.read())
    os.unlink(log)
for log in sorted(glob.glob('/tmp/ctx_err.*')):
    with open(log) as f:
        err = f.read()
        if err.strip(): print(f"ERRORS:\n{err}")
    os.unlink(log)
os.close(fd); os.waitpid(pid, 0)
