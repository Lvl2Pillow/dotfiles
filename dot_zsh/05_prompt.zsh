# Performant prompt using async + SIGUSR1 for instant redraw.
# <working_dir> <git_branch> <symbol>

_prompt_is_git_cache=0
_prompt_git_dir_cache=""
_prompt_dir_cache=""
_prompt_dir_out=""
_prompt_branch_out=""
_prompt_git_staged=0
_prompt_git_unstaged=0
_prompt_git_last_pid=0
_prompt_async_counter=0
_prompt_async_out="/tmp/prompt_async_out_$$"
_prompt_rendering=0
_prompt_last_exit=0

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
    if [[ -d "$current/.git" ]]; then
      _prompt_git_dir_cache="$current/.git"
      _prompt_is_git_cache=1
      return 0
    elif [[ -f "$current/.git" ]]; then
      # git worktree
      local line
      IFS= read -r line < "$current/.git" || { _prompt_is_git_cache=0; return 1; }
      if [[ "$line" == gitdir:\ * ]]; then
        local git_dir="${line#gitdir: }"
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
  local dir_cap="$2"

  if (( ${#dir_raw} <= dir_cap )); then
    _prompt_dir_out="$dir_raw"
    return 0
  fi

  local beginning="${dir_raw:0:2}"
  local ending_len=$(( dir_cap - 5 ))
  local ending="${dir_raw: -$ending_len}"
  _prompt_dir_out="${beginning}...${ending}"
}

function _prompt_truncate_branch() {
  local branch="$1"
  local branch_cap="$2"

  if (( ${#branch} <= branch_cap )); then
    _prompt_branch_out="$branch"
    return 0
  fi

  local ending="${branch: -5}"
  local beginning_len=$(( branch_cap - 8 ))
  local beginning="${branch:0:$beginning_len}"
  _prompt_branch_out="${beginning}...${ending}"
}

function _prompt_async_git_start() {
  [[ $_prompt_git_last_pid -gt 0 ]] && kill $_prompt_git_last_pid 2>/dev/null
  _prompt_async_counter=$(( _prompt_async_counter + 1 ))
  (
    cd "$1" 2>/dev/null || exit
    local staged=0
    local unstaged=0
    git diff-index --cached --quiet HEAD 2>/dev/null || staged=1
    git --no-optional-locks diff-files --quiet 2>/dev/null || unstaged=1
    echo "$staged|$unstaged|$_prompt_async_counter" > "${_prompt_async_out}_volatile"
    mv "${_prompt_async_out}_volatile" "$_prompt_async_out"
    # signal parent to redraw prompt immediately
    kill -s USR1 $$ 2>/dev/null
  ) &!
  _prompt_git_last_pid=$!
}

# consume async result file if it exists
function _prompt_signal_handler() {
  [[ ! -f $_prompt_async_out ]] && return
  local line
  IFS= read -r line < "$_prompt_async_out" || return
  rm -f "$_prompt_async_out"
  local parts=("${(@s:|:)line}")
  [[ $parts[3] != $_prompt_async_counter ]] && return   # stale
  _prompt_git_staged=$parts[1]
  _prompt_git_unstaged=$parts[2]
}

TRAPUSR1() {
  _prompt_rendering=1
  _prompt_precmd
  _prompt_rendering=0
  zle .reset-prompt 2>/dev/null
}

autoload -Uz add-zsh-hook

_prompt_precmd() {
  local last_exit=$?  # capture exit status before anything changes it
  if (( ! _prompt_rendering )); then
    _prompt_last_exit=$last_exit
  fi

  _prompt_signal_handler

  local MIN_DIR=36
  local MIN_BRANCH=40
  # MIN_TOTAL = 36 + space + 40 + space + symbol + space = 80

  local DIR_COLOR='%F{135}'     # purple
  local BRANCH_COLOR='%F{112}'  # lime — clean (default)
  if (( _prompt_git_unstaged )); then
    BRANCH_COLOR='%F{208}'      # orange — unstaged (highest priority)
  elif (( _prompt_git_staged )); then
    BRANCH_COLOR='%F{220}'      # yellow — staged
  fi

  local SYMBOL_COLOR=''  # default foreground (white) on success
  if (( _prompt_last_exit )); then
    SYMBOL_COLOR='%F{196}'  # bright red (#ff0000) on failure
  fi

  local extra=0
  if [[ -n "$COLUMNS" ]]; then
      local extra=$(( $COLUMNS > 80 ? $COLUMNS - 80 : 0 ))
  fi

  local branch_raw=""
  if _prompt_git_branch; then
    branch_raw="$_prompt_branch_out"
    (( _prompt_rendering )) || _prompt_async_git_start "$PWD"
  fi
  local extra_needed=0
  if [[ -n "$branch_raw" ]]; then
    local branch_len=${#branch_raw}
    extra_needed=$(( branch_len > MIN_BRANCH ? branch_len - MIN_BRANCH : 0 ))
  fi

  local extra_allocated=$(( extra < extra_needed ? extra : extra_needed ))
  local extra_remaining=$(( extra - extra_allocated ))
  local branch_cap=$(( MIN_BRANCH + extra_allocated ))
  local dir_cap=$(( MIN_DIR + extra_remaining ))

  local dir_raw="${PWD/#$HOME/~}"

  _prompt_truncate_dir "$dir_raw" "$dir_cap"
  # replace % with %% otherwise will be interpreted as an escape character
  local dir_sanitized="${_prompt_dir_out//\%/%%}"

  if [[ -n "$branch_raw" ]]; then
    _prompt_truncate_branch "$branch_raw" "$branch_cap"
    local branch_sanitized="${_prompt_branch_out//\%/%%}"
    PROMPT="${DIR_COLOR}${dir_sanitized}%f ${BRANCH_COLOR}${branch_sanitized}%f ${SYMBOL_COLOR}%(#.#.%%)%f "
  else
    PROMPT="${DIR_COLOR}${dir_sanitized}%f ${SYMBOL_COLOR}%(#.#.%%)%f "
  fi
}
add-zsh-hook precmd _prompt_precmd

# cleanup on exit - removes FIFO, kills worker, no "bg running" warning
_prompt_cleanup() {
  rm -f $_prompt_async_out "${_prompt_async_out}_volatile"
  [[ $_prompt_git_last_pid -gt 0 ]] && kill $_prompt_git_last_pid 2>/dev/null
}
add-zsh-hook zshexit _prompt_cleanup
