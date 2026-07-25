"""Probe: check ZLE status inside _prompt_zle_append_footer and if POSTDISPLAY write succeeds."""
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
_logf=/tmp/zle_test.$$
echo "PID=$$" >&2

# Override with exact same logic but logging before/after each step
_prompt_zle_append_footer() {
  emulate -L zsh
  local zl
  if zle 2>/dev/null; then zl=Y; else zl=N; fi
  echo "F:WIDGET=[$WIDGET] ZLE=$zl" >> $_logf
  [[ -z "$_prompt" ]] && return 0
  [[ $WIDGET = *accept-line* ]] && { echo "  SKIP_ACCEPT" >> $_logf; return 0; }
  for pos in $_prompt_rh_positions; do
    { region_highlight=("${(@)region_highlight:#${pos} *}") } 2>/dev/null
  done
  _prompt_rh_positions=()
  echo "  RH_CLEAR" >> $_logf
  local ghost="${POSTDISPLAY%%$'\n'*}" 2>/dev/null
  : "${ghost:=}"
  echo "  GHOST=[${ghost}]" >> $_logf
  { POSTDISPLAY="${ghost}"$'\n'"${_prompt}" } 2>/dev/null
  echo "  PD_WRITTEN" >> $_logf
  local -i prompt_start=$(( ${#BUFFER} + ${#POSTDISPLAY} - ${#_prompt} ))
  local -i prompt_end=$(( prompt_start + ${#_prompt} ))
  local -i dir_end=$(( prompt_start + _prompt_dir_len ))
  local dir_entry="${prompt_start} ${dir_end} bold,${_prompt_rh_colors[1]}"
  { region_highlight+=("${dir_entry}") } 2>/dev/null
  if (( ${#_prompt_rh_colors[@]} > 1 )); then
    local -i branch_start=$(( dir_end + 1 ))
    local branch_entry="${branch_start} ${prompt_end} bold,${_prompt_rh_colors[2]}"
    { region_highlight+=("${branch_entry}") } 2>/dev/null
  fi
  echo "  DONE colors=[${_prompt_rh_colars[*]}]" >> $_logf
}
'''

for f in glob.glob('/tmp/zle_test.*'): os.unlink(f)

CHEZMOI = os.path.expanduser('~/.local/share/chezmoi')
pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
    d = f'/tmp/zsh_probe_{os.getpid()}'; os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config + '\n')
    os.environ['ZDOTDIR'] = d
    os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)

time.sleep(1.0); read_all(fd, 0.5)
os.write(fd, f'cd {CHEZMOI}\n'.encode())
time.sleep(3.0); read_all(fd, 3.0)

os.close(fd); os.waitpid(pid, 0)

for log in sorted(glob.glob('/tmp/zle_test.*')):
    with open(log) as f: print(f.read())
    os.unlink(log)
