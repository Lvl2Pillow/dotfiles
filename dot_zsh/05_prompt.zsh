# Performant prompt that behaves as transient footer below cursor row.
# Compatible with autosuggestions.
# <symbol> <cursor> ...
# <working_dir> <git_branch> (below buffer)

# Short-circuit prompt when non-interactive. Tests can set _PROMPT_FORCE_LOAD=1 to bypass.
[[ (! -o interactive || ! -o MONITOR) && -z $_PROMPT_FORCE_LOAD ]] && {
  PROMPT='%# '
  return 0
}

_PROMPT_DIR_MIN=10
_PROMPT_BRANCH_MIN=15

_prompt_is_git_cache=0
_prompt_git_dir_cache=""
_prompt_dir_cache=""
_prompt_dir_out=""
_prompt_branch_out=""
_prompt_git_staged=0
_prompt_git_unstaged=0
_prompt_git_untracked=0
_prompt_git_stashed=0
_prompt_git_last_pid=0
_prompt_async_counter=0
_prompt_async_out="/tmp/prompt_async_out_$$"
_prompt_rendering=0
_prompt_last_exit=0
_prompt=""
_prompt_dir_len=0
_prompt_rh_colors=()
_prompt_rh_entries=()

# handle async updates
TRAPUSR1() {
  emulate -L zsh
  _prompt_rendering=1
  _prompt_precmd
  _prompt_rendering=0
  zle .reset-prompt 2>/dev/null
}

# handle Ctrl+C
TRAPINT() {
  emulate -L zsh
  # whether in zle (otherwise during command execution)
  if zle; then
    # cursor down, clear footer row, then move up 2 rows to negate zle's \033[1B and gap
    printf '\033[1B\033[2K\033[2A'
    return $(( 128 + $1 ))
  fi
  return 0
}

# manually walk up tree to find .git/
function _prompt_find_git() {
  if [[ "$PWD" == "$_prompt_dir_cache" ]]; then
    if (( _prompt_is_git_cache )); then
      if [[ -f "$_prompt_git_dir_cache/HEAD" ]]; then
        return 0
      fi
      # lost .git/HEAD - invalidate and re-walk
      _prompt_is_git_cache=0
      _prompt_git_dir_cache=""
      _prompt_dir_cache=""
    else
      return 1
    fi
  fi

  _prompt_dir_cache="$PWD"

  local current="$PWD"
  while [[ "$current" != "/" ]]; do
    if [[ -d "$current/.git" && -f "$current/.git/HEAD" ]]; then
      _prompt_git_dir_cache="$current/.git"
      _prompt_is_git_cache=1
      return 0
    elif [[ -f "$current/.git" ]]; then
      # git worktree
      local line
      IFS= read -r line < "$current/.git" || { _prompt_is_git_cache=0; return 1; }
      if [[ "$line" == gitdir:\ * ]]; then
        local git_dir="${${line#gitdir: }:A}"
        if [[ -d "$git_dir" ]]; then
          _prompt_is_git_cache=1
          _prompt_git_dir_cache="$git_dir"
          return 0
        fi
      fi
      _prompt_is_git_cache=0
      return 1
    fi
    current="${current:h}"
  done

  _prompt_is_git_cache=0
  return 1
}

function _prompt_git_branch() {
  if ! _prompt_find_git; then
    _prompt_branch_out=""
    return 1
  fi

  local git_head
  IFS= read -r git_head < "$_prompt_git_dir_cache/HEAD" || return 1

  if [[ "$git_head" == ref:\ refs/heads/* ]]; then
      # normal HEAD
    _prompt_branch_out="${git_head#ref: refs/heads/}"
    return 0
  else
      # detached HEAD
    _prompt_branch_out="@${git_head:0:7}"
  fi
  return 0
}

function _prompt_truncate_dir() {
  local dir_raw="$1"
  local -i dir_cap=$2

  # handle small terminal
  if (( dir_cap < _PROMPT_DIR_MIN )); then
    # no ellipsis, just truncate front
    _prompt_dir_out="${dir_raw: -$dir_cap}"
    return 0
  fi

  if (( ${#dir_raw} <= dir_cap )); then
    _prompt_dir_out="$dir_raw"
    return 0
  fi

  local beginning="${dir_raw:0:2}"
  local -i ending_len=$(( dir_cap - 5 ))
  local ending="${dir_raw: -$ending_len}"
  _prompt_dir_out="${beginning}...${ending}"
}

function _prompt_truncate_branch() {
  local branch="$1"
  local -i branch_cap=$2

  # handle small terminal
  if (( branch_cap < _PROMPT_BRANCH_MIN )); then
      # no ellipsis, just truncate back
      _prompt_branch_out="${branch:0:$branch_cap}"
      return 0
  fi

  if (( ${#branch} <= branch_cap )); then
    _prompt_branch_out="$branch"
    return 0
  fi

  local ending="${branch: -2}"
  local -i beginning_len=$(( branch_cap - 5 ))
  local beginning="${branch:0:$beginning_len}"
  _prompt_branch_out="${beginning}...${ending}"
}

function _prompt_async_git_start() {
  [[ $_prompt_git_last_pid -gt 0 ]] && kill -- -$_prompt_git_last_pid 2>/dev/null
  _prompt_async_counter=$(( _prompt_async_counter + 1 ))
  (
    cd "$1" 2>/dev/null || exit
    local -i staged=0
    local -i unstaged=0
    local -i untracked=0
    local -i stashed=0
    if [[ -n $IS_MANAGED ]]; then
      git --no-optional-locks diff --cached --quiet 2>/dev/null
      (( $? == 1 )) && staged=1
      git --no-optional-locks diff --quiet 2>/dev/null
      (( $? == 1 )) && unstaged=1
    else
      git --no-optional-locks status --porcelain --ignore-submodules=all --untracked-files=normal --no-renames > "${_prompt_async_out}_status" 2>/dev/null || exit
      while IFS= read -r line; do
        [[ ${line[1]} != ' ' && ${line[1]} != '?' ]] && staged=1
        [[ ${line[2]} != ' ' && ${line[2]} != '?' ]] && unstaged=1
        [[ ${line} = '??'* ]] && untracked=1
        (( staged && unstaged )) && break
      done < "${_prompt_async_out}_status"
    fi
    if (( staged + unstaged + untracked == 0 )); then
        git rev-parse --verify --quiet refs/stash &>/dev/null && stashed=1
    fi
    echo "$staged|$unstaged|$untracked|$stashed|$_prompt_async_counter" > "${_prompt_async_out}_volatile"
    mv "${_prompt_async_out}_volatile" "$_prompt_async_out"
    # signal parent to redraw prompt immediately
    kill -s USR1 $$ 2>/dev/null
  ) &!
  _prompt_git_last_pid=$!
}

# consume async result file if it exists
function _prompt_signal_handler() {
  [[ ! -f $_prompt_async_out ]] && return 0
  local line
  IFS= read -r line < "$_prompt_async_out" || return 0
  rm -f "$_prompt_async_out"
  local parts=("${(@s:|:)line}")
  [[ $parts[5] != $_prompt_async_counter ]] && return 0 # stale
  _prompt_git_staged=$parts[1]
  _prompt_git_unstaged=$parts[2]
  _prompt_git_untracked=$parts[3]
  _prompt_git_stashed=$parts[4]
}

autoload -Uz add-zsh-hook

_prompt_precmd() {
  emulate -L zsh
  local -i last_exit=$?  # capture exit status before anything changes it
  if (( ! _prompt_rendering )); then
    _prompt_last_exit=$last_exit
  fi

  _prompt_signal_handler

  local -i cols=${COLUMNS:-80}

  local DIR_COLOR='fg=135'     # purple
  local BRANCH_COLOR='fg=34'   # green — clean (default)
  if (( _prompt_git_untracked )); then
    BRANCH_COLOR='fg=88'       # dark red — untracked
  elif (( _prompt_git_unstaged )); then
    BRANCH_COLOR='fg=208'      # orange — unstaged
  elif (( _prompt_git_staged )); then
    BRANCH_COLOR='fg=220'      # yellow — staged
  elif (( _prompt_git_stashed )); then
    BRANCH_COLOR='fg=112'      # lime — stashed
  fi

  local SYMBOL_COLOR=''        # default foreground (white) on success
  if (( _prompt_last_exit )); then
    SYMBOL_COLOR='%F{196}'     # bright red (#ff0000) on failure
  fi

  local dir_raw="${PWD/#$HOME/~}"
  local -i dir_len=${#dir_raw}

  local branch_raw=""
  if _prompt_git_branch; then
    branch_raw="$_prompt_branch_out"
    (( _prompt_rendering )) || _prompt_async_git_start "$PWD"
  fi

  local -i dir_cap
  local -i branch_cap
  if [[ -n "$branch_raw" ]]; then
    local -i available=$(( cols - 1 ))
    local -i branch_len=${#branch_raw}
    dir_cap=$(( available * dir_len / (dir_len + branch_len) ))
    branch_cap=$(( available - dir_cap ))
    if (( cols >= _PROMPT_DIR_MIN + _PROMPT_BRANCH_MIN + 1 )); then
        if (( dir_cap < _PROMPT_DIR_MIN )); then
            dir_cap=$_PROMPT_DIR_MIN
            branch_cap=$(( available - dir_cap ))
        fi
        if (( branch_cap < _PROMPT_BRANCH_MIN )); then
            branch_cap=$_PROMPT_BRANCH_MIN
            dir_cap=$(( available - dir_cap ))
        fi
    fi
  else
    dir_cap=$cols
    branch_cap=0
  fi

  _prompt_truncate_dir "$dir_raw" $dir_cap
  # replace % with %% otherwise will be interpreted as an escape character
  local dir_sanitized="${_prompt_dir_out//\%/%%}"
  _prompt_dir_len=${#dir_sanitized}

  if [[ -n "$branch_raw" ]]; then
    _prompt_truncate_branch "$branch_raw" $branch_cap
    local branch_sanitized="${_prompt_branch_out//\%/%%}"
    _prompt="${dir_sanitized} ${branch_sanitized}"
    _prompt_rh_colors=("${DIR_COLOR}" "${BRANCH_COLOR}")
  else
    _prompt="${dir_sanitized}"
    _prompt_rh_colors=("${DIR_COLOR}")
  fi

  # PROMPT is just symbol; the rest goes into the footer
  PROMPT="%B${SYMBOL_COLOR}%(#.#.%%)%f %b"
}
add-zsh-hook precmd _prompt_precmd

# prevent autosuggestions from rebinding on precmd (would undo our wrapping)
add-zsh-hook -d precmd _zsh_autosuggest_start 2>/dev/null

# preserve any existing accept-line wrapper (e.g. autosuggestions' clear handler)
if zle -l accept-line 2>/dev/null; then
  zle -A accept-line _prompt_orig_accept_line
fi
_prompt_zle_accept_line() {
  emulate -L zsh
  # clear POSTDISPLAY on accept-line so footer is gone before command runs
  POSTDISPLAY=
  if zle -l _prompt_orig_accept_line 2>/dev/null; then
    zle _prompt_orig_accept_line
  else
    zle .accept-line
  fi
}
zle -N accept-line _prompt_zle_accept_line

_prompt_zle_ctrlc() {
  emulate -L zsh
  POSTDISPLAY=
  # clear autosuggestions state if present (normally done by send-break wrapper)
  if (( ${+functions[_zsh_autosuggest_clear]} )); then
    _zsh_autosuggest_clear
  fi
  zle .send-break
  # display fresh prompt
  zle .reset-prompt
}
zle -N _prompt_zle_ctrlc
bindkey '^C' _prompt_zle_ctrlc

# wrap _zsh_autosuggest_highlight_apply to append prompt footer after ghost text.
if (( ${+functions[_zsh_autosuggest_highlight_apply]} )); then
  functions[_zsh_autosuggest_highlight_apply_orig]=$functions[_zsh_autosuggest_highlight_apply]
  _zsh_autosuggest_highlight_apply() {
    _zsh_autosuggest_highlight_apply_orig "$@"
    _prompt_zle_append_footer
  }
fi

# zle-line-init: set initial POSTDISPLAY
_prompt_zle_line_init() {
  emulate -L zsh
  _prompt_zle_append_footer
}
zle -N zle-line-init _prompt_zle_line_init

# zle-line-pre-redraw: ensure footer after autosuggestions
_prompt_zle_line_pre_redraw() {
  emulate -L zsh
  _prompt_zle_append_footer
}
# only register if autosuggestions is not wrapping highlights
if (( ! ${+functions[_zsh_autosuggest_highlight_apply]} )); then
  zle -N zle-line-pre-redraw _prompt_zle_line_pre_redraw
fi

# append prompt footer to POSTDISPLAY (preserving ghost text) and set region_highlight
_prompt_zle_append_footer() {
  emulate -L zsh
  [[ -z "$_prompt" ]] && return 0

  local entry
  for entry in $_prompt_rh_entries; do
    region_highlight=("${(@)region_highlight:#$entry}")
  done
  _prompt_rh_entries=()

  # append footer to POSTDISPLAY if not already present
  if [[ "${POSTDISPLAY}" != *$'\n'"${_prompt}" ]]; then
    POSTDISPLAY="${POSTDISPLAY}"$'\n'"${_prompt}"
  fi

  local -i prompt_start=$(( ${#BUFFER} + ${#POSTDISPLAY} - ${#_prompt} ))
  local -i prompt_end=$(( prompt_start + ${#_prompt} ))
  local -i dir_end=$(( prompt_start + _prompt_dir_len ))

  local dir_entry="${prompt_start} ${dir_end} bold,${_prompt_rh_colors[1]}"
  region_highlight+=("${dir_entry}")
  _prompt_rh_entries+=("${dir_entry}")

  if (( ${#_prompt_rh_colors[@]} > 1 )); then
    local -i branch_start=$(( dir_end + 1 ))
    local branch_entry="${branch_start} ${prompt_end} bold,${_prompt_rh_colors[2]}"
    region_highlight+=("${branch_entry}")
    _prompt_rh_entries+=("${branch_entry}")
  fi
}

# cleanup on exit - removes temp file, kills async, no "bg process running" warning
_prompt_cleanup() {
  emulate -L zsh
  rm -f $_prompt_async_out "${_prompt_async_out}_volatile" "${_prompt_async_out}_status"
  [[ $_prompt_git_last_pid -gt 0 ]] && kill -- -$_prompt_git_last_pid 2>/dev/null
}
add-zsh-hook zshexit _prompt_cleanup

# TODO - fix autocomplete
# TODO - when pressing up history, footer loses color
# TODO - check if untracked works
