# Async Git Status (FIFO + zle -F -w)

## Setup (session lifetime)

Run once at startup in the prompt file's top-level scope:

```zsh
_prompt_async_fifo="${XDG_RUNTIME_DIR:-/tmp}/pzsh-async-$$.fifo"
rm -f "$_prompt_async_fifo"
if mkfifo "$_prompt_async_fifo" 2>/dev/null; then
    exec {_prompt_async_fd}<>"$_prompt_async_fifo"
    # fd is now open for both read and write — never closes
else
    # FIFO unsupported (read-only fs, etc.) — disable async
    _prompt_async_fd=-1
fi
```

`exec {_prompt_async_fd}<>"$fifo"` opens BOTH read and write sides. Without write side, `read` blocks forever after consuming all data (no writer, FIFO appears empty). With write side, the fd never hits EOF.

## Async start (precmd)

```zsh
_prompt_async_git_start() {
    emulate -L zsh
    if (( _prompt_async_fd < 0 )); then
        return 1
    fi
    (( _prompt_async_counter++ ))
    local fifo=$_prompt_async_fifo
    local counter=$_prompt_async_counter

    # Fork delay so zle-line-init renders the prompt first
    (
        sleep 0.05
        local -a git_status
        git_status=($(git status --porcelain 2>/dev/null))
        local rc=$?
        if (( rc > 1 )); then
            exit
        fi

        local staged=0 unstaged=0 untracked=0 stashed=0
        local line
        for line in "${git_status[@]}"; do
            case $line in
                ('?'*) (( untracked++ )) ;;
                (' '[A-Z]) (( unstaged++ )) ;;
                ([A-Z]' ') (( staged++ )) ;;
                ([A-Z][A-Z]) (( staged++ )) ;;
            esac
        done
        git status --porcelain 2>/dev/null | grep -q '^[? ]?' && (( untracked > 0 ))
        echo "${staged}|${unstaged}|${untracked}|${stashed}|${counter}" > "$fifo"
    ) &!
}
```

## zle-line-init registration (once per session)

```zsh
_prompt_zle_line_init() {
    emulate -L zsh
    _prompt_zle_append_footer
    if (( ! _prompt_zle_F_registered )); then
        zle -N _prompt_async_callback
        zle -F -w $_prompt_async_fd _prompt_async_callback
        _prompt_zle_F_registered=1
    fi
}
```

## Callback

```zsh
_prompt_async_callback() {
    local fd=$1
    local line
    if ! IFS= read -r line <&$fd; then
        return 0
    fi
    local parts=("${(@s:|:)line}")
    if [[ $parts[5] != $_prompt_async_counter ]]; then
        return 0  # stale — discard
    fi
    _prompt_git_staged=$parts[1]
    _prompt_git_unstaged=$parts[2]
    _prompt_git_untracked=$parts[3]
    _prompt_git_stashed=$parts[4]

    _prompt_rendering=1
    _prompt_precmd
    _prompt_rendering=0

    # Only colors changed, not text — just update region_highlight
    _prompt_update_region_highlight

    # zle -R prevents line-eating bug (zsh contributor fix)
    # zle .redisplay re-renders region_highlight (zsh maintainer)
    zle -R && zle .redisplay
}
```

## Counter-based stale filtering

`_prompt_async_counter` increments on every precmd. Async result includes counter as pipe-delimited field. Callback discards if mismatch:

```
t=0:  precmd → counter=1, async#1 starts in ~/repoA (dirty)
t=0.1: cd ~/repoB → precmd → counter=2, async#2 starts
t=0.3: async#1 finishes → writes "0|1|0|0|1" to FIFO
t=0.4: callback: parts[5]=1, counter=2 → DISCARD (stale for repoB)
t=0.5: async#2 finishes → writes "0|0|0|0|2"
t=0.6: callback: parts[5]=2, counter=2 → MATCH → processed
```

Without this check, async#1's dirty data would overwrite repoB's clean state → wrong orange flash.
