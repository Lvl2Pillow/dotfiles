"""Probe: check if _prompt_zle_append_footer succeeds inside TRAPUSR1."""
import os, pty, select, time, glob

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

# Patch _prompt_zle_append_footer to log before/after POSTDISPLAY assignment
config = r'''
source ~/.zshrc 2>/dev/null || true

# Log file
_logf=/tmp/pd_log.$$
_pmlog() { echo "$1" >> $_logf; }

# Re-wrap _prompt_zle_append_footer to log
_prompt_zle_append_footer() {
  emulate -L zsh
  _pmlog "ENTER WIDGET=[$WIDGET] ZLE=$(zle 2>/dev/null && echo Y || echo N)"
  [[ -z "$_prompt" ]] && { _pmlog "EXIT noprompt"; return 0; }
  [[ $WIDGET = *accept-line* ]] && { _pmlog "EXIT accept"; return 0; }
  _pmlog "BEFORE_RH"
  for pos in $_prompt_rh_positions; do
    { region_highlight=("${(@)region_highlight:#${pos} *}") } 2>/dev/null
  done
  _prompt_rh_positions=()
  _pmlog "RH_CLEARED"
  local ghost="${POSTDISPLAY%%$'\n'*}" 2>/dev/null
  : "${ghost:=}"
  _pmlog "GOT_GHOST=[${ghost}]"
  { POSTDISPLAY="${ghost}"$'\n'"${_prompt}" } 2>/dev/null
  _pmlog "PD_SET"
  local -i prompt_start=$(( ${#BUFFER} + ${#POSTDISPLAY} - ${#_prompt} ))
  local -i prompt_end=$(( prompt_start + ${#_prompt} ))
  local -i dir_end=$(( prompt_start + _prompt_dir_len ))
  local dir_entry="${prompt_start} ${dir_end} bold,${_prompt_rh_colors[1]}"
  { region_highlight+=("${dir_entry}") } 2>/dev/null
  _pmlog "RH_ADDED_DIR"
  if (( ${#_prompt_rh_colors[@]} > 1 )); then
    local -i branch_start=$(( dir_end + 1 ))
    local branch_entry="${branch_start} ${prompt_end} bold,${_prompt_rh_colors[2]}"
    { region_highlight+=("${branch_entry}") } 2>/dev/null
    _pmlog "RH_ADDED_BRANCH"
  fi
  _pmlog "EXIT_OK"
}
'''

for f in glob.glob('/tmp/pd_log.*'): os.unlink(f)

CHEZMOI_DIR = os.path.expanduser('~/.local/share/chezmoi')
pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
    d = f'/tmp/zsh_probe_{os.getpid()}'; os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config + '\n')
    os.environ['ZDOTDIR'] = d
    os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)

time.sleep(1.0); read_all(fd, 0.5)
os.write(fd, f'cd {CHEZMOI_DIR}\n'.encode())
time.sleep(2.0); read_all(fd, 3.0)

logs = sorted(glob.glob('/tmp/pd_log.*'))
for log in logs:
    with open(log) as f: print(f.read())
    os.unlink(log)
os.close(fd); os.waitpid(pid, 0)
