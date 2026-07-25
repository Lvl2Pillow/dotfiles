import os, pty, select, time, re

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

# Log ALL widget calls by patching multiple entry points
config = r'''
source ~/.zshrc 2>/dev/null || true

typeset -g _pm_logfile=/tmp/widget_full.$$

_pmlog() { echo "$1" >> $_pm_logfile; }

_pmlog "=== START ==="

# Patch zle-init and zle-redraw hooks
_prompt_zle_append_footer() {
  emulate -L zsh
  _pmlog "APPEND_FOOTER:WIDGET=[$WIDGET]"
  [[ -z "$_prompt" ]] && { _pmlog "  skip: no _prompt"; return 0; }
  zle 2>/dev/null && ZLEV=Y || ZLEV=N
  _pmlog "  zle=$ZLEV"
  [[ $ZLEV = N ]] && { _pmlog "  skip: not in ZLE"; return 0; }
  [[ $WIDGET = *accept-line* ]] && { _pmlog "  skip: accept-line"; return 0; }
  _pmlog "  APPENDING FOOTER"
  return 0
}

# Also log when autosuggest highlight_apply runs
if (( ${+functions[_zsh_autosuggest_highlight_apply]} )); then
  _zsh_autosuggest_highlight_apply() {
    _pmlog "HIGHLIGHT_APPLY:WIDGET=[$WIDGET]"
    # Don't call original - we patched _prompt_zle_append_footer which captures everything
  }
fi

_pmlog "=== PATCH DONE ==="
'''

import glob
for f in glob.glob('/tmp/widget_full.*'): os.unlink(f)

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
    d = f'/tmp/zsh_probe8_{os.getpid()}'; os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config + '\n')
    os.environ['ZDOTDIR'] = d
    os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)

time.sleep(1.5); read_all(fd, 0.3)
os.write(fd, b'\n'); time.sleep(0.5)
read_all(fd, 0.3)

for log in sorted(glob.glob('/tmp/widget_full.*')):
    with open(log) as f:
        print(f.read())
    os.unlink(log)
os.close(fd); os.waitpid(pid, 0)
