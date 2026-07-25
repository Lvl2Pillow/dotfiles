#!/bin/zsh
echo "ZSH_VERSION=$ZSH_VERSION"
typeset -p POSTDISPLAY 2>&1 || echo "POSTDISPLAY not set"
echo "zle exists: $(zle -l 2>/dev/null | wc -l)"
