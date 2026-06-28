# don't save less history
export LESSHISTFILE=-

# timestamp history
export HISTTIMEFORMAT="[%F %T] "
setopt EXTENDED_HISTORY
setopt INC_APPEND_HISTORY

# XDG
export YARN_CACHE_FOLDER="$HOME/.cache/yarn"
export YARN_RC_FILENAME="$HOME/.config/yarn/yarnrc"
export NPM_CONFIG_CACHE="$HOME/.cache/npm"
export NPM_CONFIG_USERCONFIG="$HOME/.config/npm/npmrc"
