# Performant prompt that behaves like a transient footer below cursor + buffer row.
# Compatible with autocomplete.
# ```
# <symbol> <cursor> <buffer>\n
# <working_dir> <git_branch>
# ```

# Short-circuit prompt when non-interactive.
# Tests can set _PROMPT_FORCE_LOAD=1 to bypass.
if [[ (! -o interactive || ! -o MONITOR) && -z $_PROMPT_FORCE_LOAD ]]; then
    PROMPT='%# '
    return 0
fi

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
_prompt_zle_fd_registered=0
_prompt_rerendering=0
_prompt_last_exit=0
_prompt_ctrl_c=0
_prompt=""
_prompt_dir_len=0
_prompt_rh_colors=()
_prompt_rh_positions=()

# Create FIFO for async git status result delivery
# zle -F watches the read-end; child processes write by pathname
rm -f "${TMPDIR:-/tmp}/prompt_async_fifo_$$"
_prompt_async_fifo="${TMPDIR:-/tmp}/prompt_async_fifo_$$"
mkfifo "$_prompt_async_fifo"
exec {_prompt_async_fd}<>"$_prompt_async_fifo"

# Manually walk up tree to find .git/
# Faster than git commands
function _prompt_find_git() {
    if [[ "$PWD" == "$_prompt_dir_cache" ]]; then
        if (( _prompt_is_git_cache )); then
            if [[ -f "$_prompt_git_dir_cache/HEAD" && -r "$_prompt_git_dir_cache/HEAD" ]]; then
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
        if [[ -d "$current/.git" && -f "$current/.git/HEAD" && -r "$current/.git/HEAD" ]]; then
            _prompt_git_dir_cache="$current/.git"
            _prompt_is_git_cache=1
            return 0
        elif [[ -f "$current/.git" && -r "$current/.git" ]]; then
            # git worktree
            local line
            if ! IFS= read -r line < "$current/.git"; then
                _prompt_is_git_cache=0
                return 1
            fi
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
    if ! IFS= read -r git_head < "$_prompt_git_dir_cache/HEAD"; then
        return 1
    fi

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
    if [[ $_prompt_git_last_pid -gt 0 ]]; then
        kill -- -$_prompt_git_last_pid 2>/dev/null
    fi
    _prompt_async_counter=$(( _prompt_async_counter + 1 ))
    (
        if ! cd "$1" 2>/dev/null; then
            exit
        fi
        local -i staged=0
        local -i unstaged=0
        local -i untracked=0
        local -i stashed=0
        if [[ -n $IS_MANAGED ]]; then
            git --no-optional-locks diff --cached --quiet
            if (( $? == 1 )); then
                staged=1
            fi
            git --no-optional-locks diff --quiet
            if (( $? == 1 )); then
                unstaged=1
            fi
        else
            local status_output=$(git --no-optional-locks status --porcelain --ignore-submodules=all --untracked-files=normal --no-renames 2>/dev/null)
            if (( $? > 1 )); then
                exit
            fi
            while IFS= read -r line; do
                if [[ ${line[1]} != ' ' && ${line[1]} != '?' ]]; then
                    staged=1
                fi
                if [[ ${line[2]} != ' ' && ${line[2]} != '?' ]]; then
                    unstaged=1
                fi
                if [[ ${line} = '??'* ]]; then
                    untracked=1
                fi
                if (( staged && unstaged )); then
                    break
                fi
            done <<< "$status_output"
        fi
        if (( staged + unstaged + untracked == 0 )); then
            git rev-parse --verify --quiet refs/stash &>/dev/null
            if (( $? == 0 )); then
                stashed=1
            fi
        fi
        # Write result to FIFO — zle -F callback picks it up in zle context
        echo "$staged|$unstaged|$untracked|$stashed|$_prompt_async_counter" > "$_prompt_async_fifo"
    ) &!
    _prompt_git_last_pid=$!
}

autoload -Uz add-zsh-hook

_prompt_precmd() {
    local -i last_exit=$?  # capture exit status before anything changes it
    emulate -L zsh
    if (( ! _prompt_rerendering )); then
        _prompt_last_exit=$last_exit
    fi

    local -i cols=${COLUMNS:-80}

    local DIR_COLOR='fg=135'     # purple
    local BRANCH_COLOR='fg=34'   # green - clean (default)
    if (( _prompt_git_untracked )); then
        BRANCH_COLOR='fg=88'       # dark red - untracked
    elif (( _prompt_git_unstaged )); then
        BRANCH_COLOR='fg=208'      # orange - unstaged
    elif (( _prompt_git_staged )); then
        BRANCH_COLOR='fg=220'      # yellow - staged
    elif (( _prompt_git_stashed )); then
        BRANCH_COLOR='fg=112'      # lime - stashed
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
        if (( ! _prompt_rerendering )); then
            _prompt_async_git_start "$PWD"
        fi
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

    # zle does not have ctrl+c widget so instead we handle it just before printing new prompt
    if (( _prompt_ctrl_c )); then
        # cursor up, delete line (old prompt footer)
        printf '\033[A\033[2K'
        _prompt_ctrl_c=0
    fi

    # PROMPT is just symbol; the rest goes into the footer
    PROMPT="%B${SYMBOL_COLOR}%(#.#.%%)%f %b"
}
add-zsh-hook precmd _prompt_precmd

# Recompute region_highlight positions from current BUFFER / POSTDISPLAY
_prompt_update_region_highlight() {
    # remove old entries
    for pos in $_prompt_rh_positions; do
        region_highlight=("${(@)region_highlight:#${pos} *}")
    done
    _prompt_rh_positions=()

    local -i prompt_start=$(( ${#BUFFER} + ${#POSTDISPLAY} - ${#_prompt} ))
    local -i prompt_end=$(( prompt_start + ${#_prompt} ))
    local -i dir_end=$(( prompt_start + _prompt_dir_len ))

    local dir_entry="${prompt_start} ${dir_end} bold,${_prompt_rh_colors[1]}"
    region_highlight+=("${dir_entry}")
    _prompt_rh_positions+=("${prompt_start} ${dir_end}")

    if (( ${#_prompt_rh_colors[@]} > 1 )); then
        local -i branch_start=$(( dir_end + 1 ))
        local branch_entry="${branch_start} ${prompt_end} bold,${_prompt_rh_colors[2]}"
        region_highlight+=("${branch_entry}")
        _prompt_rh_positions+=("${branch_start} ${prompt_end}")
    fi
}

# Append prompt footer to POSTDISPLAY (preserving ghost text) and set region_highlight
_prompt_zle_append_footer() {
    emulate -L zsh
    # skip when accepting a line - the session is ending, no need to append footer
    if [[ $WIDGET = *accept-* ]]; then
        return 0
    fi

    # strip old footer, keep only ghost text (before first \n)
    local ghost="${POSTDISPLAY%%$'\n'*}"
    POSTDISPLAY="${ghost}"$'\n'"${_prompt}"

    _prompt_update_region_highlight
}

# Update region_highlight positions on every keystroke
_prompt_zle_pre_redraw() {
    emulate -L zsh
    if [[ $WIDGET = *accept-* ]]; then
        return 0
    fi

    _prompt_update_region_highlight
}

_prompt_async_callback() {
    local fd=$1
    local line
    if ! IFS= read -r line <&$fd; then
        return 0
    fi
    local parts=("${(@s:|:)line}")
    if [[ $parts[5] != $_prompt_async_counter ]]; then
        return 0 # stale
    fi
    _prompt_git_staged=$parts[1]
    _prompt_git_unstaged=$parts[2]
    _prompt_git_untracked=$parts[3]
    _prompt_git_stashed=$parts[4]

    # Recompute and redisplay
    _prompt_rerendering=1
    _prompt_precmd
    _prompt_rerendering=0
    _prompt_update_region_highlight
    zle .redisplay
}

_prompt_zle_accept_line() {
    emulate -L zsh
    # clear prompt footer (and autocomplete ghost) on accept-line (Enter)
    POSTDISPLAY=
    zle .accept-line
}
# autocomplete also clears POSTDISPLAY
if ! (( ${+functions[_zsh_autosuggest_highlight_apply]} )); then
    zle -N accept-line _prompt_zle_accept_line
fi

# Handle Esc + Enter self-insert-unmeta
_prompt_esc_enter_newline() {
    emulate -L zsh
    # default is '\r' which desyncs zle cursor tracking
    LBUFFER+=$'\n'
}
zle -N _prompt_esc_enter_newline
bindkey '^[^M' _prompt_esc_enter_newline

# Set initial POSTDISPLAY and register zle -F once
_prompt_zle_line_init() {
    emulate -L zsh
    _prompt_zle_append_footer
    if (( ! _prompt_zle_fd_registered )); then
        zle -N _prompt_async_callback
        zle -F -w $_prompt_async_fd _prompt_async_callback
        _prompt_zle_fd_registered=1
    fi
}
zle -N zle-line-init _prompt_zle_line_init

# Bind once on first precmd only
ZSH_AUTOSUGGEST_MANUAL_REBIND=1

# Append prompt footer after ghost text
if (( ${+functions[_zsh_autosuggest_highlight_apply]} )); then
    functions[_zsh_autosuggest_highlight_apply_orig]=$functions[_zsh_autosuggest_highlight_apply]
    _zsh_autosuggest_highlight_apply() {
        _zsh_autosuggest_highlight_apply_orig "$@"
        _prompt_zle_append_footer
    }
else
    # when autosuggest absent, update region_highlight on every keystroke via pre-redraw
    zle -N zle-line-pre-redraw _prompt_zle_pre_redraw
fi

# Intercept autosuggest accept / partial_accept / execute and strip out prompt footer
if (( ${+functions[_zsh_autosuggest_accept]} )); then
    # prevent infinite loop when file sourced again
    if (( ! ${+functions[_prompt_autosuggest_accept_orig]} )); then
        functions[_prompt_autosuggest_accept_orig]=$functions[_zsh_autosuggest_accept]
    fi
    _zsh_autosuggest_accept() {
        POSTDISPLAY="${POSTDISPLAY%%$'\n'*}"
        _prompt_autosuggest_accept_orig "$@"
    }
fi

if (( ${+functions[_zsh_autosuggest_partial_accept]} )); then
    if (( ! ${+functions[_prompt_autosuggest_partial_accept_orig]} )); then
        functions[_prompt_autosuggest_partial_accept_orig]=$functions[_zsh_autosuggest_partial_accept]
    fi
    _zsh_autosuggest_partial_accept() {
        POSTDISPLAY="${POSTDISPLAY%%$'\n'*}"
        _prompt_autosuggest_partial_accept_orig "$@"
    }
fi

if (( ${+functions[_zsh_autosuggest_execute]} )); then
    if (( ! ${+functions[_prompt_autosuggest_execute_orig]} )); then
        functions[_prompt_autosuggest_execute_orig]=$functions[_zsh_autosuggest_execute]
    fi
    _zsh_autosuggest_execute() {
        POSTDISPLAY="${POSTDISPLAY%%$'\n'*}"
        _prompt_autosuggest_execute_orig "$@"
    }
fi

if (( ${+functions[_zsh_autosuggest_modify]} )); then
    if (( ! ${+functions[_prompt_autosuggest_modify_orig]} )); then
        functions[_prompt_autosuggest_modify_orig]=$functions[_zsh_autosuggest_modify]
    fi
    _zsh_autosuggest_modify() {
        if [[ $WIDGET = *accept-* ]]; then
            POSTDISPLAY="${POSTDISPLAY%%$'\n'*}"
        fi
        _prompt_autosuggest_modify_orig "$@"
    }
fi

# Handle Ctrl+C
TRAPINT() {
    emulate -L zsh
    _prompt_ctrl_c=1
    _prompt_last_exit=$(( 128 + $1 ))
    return $_prompt_last_exit
}

# Cleanup on exit - close FIFO, kill async
_prompt_cleanup() {
    emulate -L zsh
    exec {_prompt_async_fd}>&-
    rm -f "$_prompt_async_fifo"
    if [[ $_prompt_git_last_pid -gt 0 ]]; then
        kill -- -$_prompt_git_last_pid 2>/dev/null
    fi
}
add-zsh-hook zshexit _prompt_cleanup
