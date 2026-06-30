fpath=($HOME/.zsh/completions $fpath)

ZSH_COMPDUMP="${ZDOTDIR:-$HOME}/.zcompdump"

autoload -Uz compinit
# read from cache; update once every 24h
if [[ -f "$ZSH_COMPDUMP" && -n "$(find "$ZSH_COMPDUMP" -mtime +1 2>/dev/null)" ]]; then
    compinit
else
    compinit -C
fi
