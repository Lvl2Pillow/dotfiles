emulate -L zsh 2>/dev/null
PROMPT='%# '
chpwd() {}

# Clear markers on initial startup
: > /tmp/zle_markers

TRAPINT() {
  emulate -L zsh
  if zle; then
    echo "TRAPINT" >> /tmp/zle_markers
  fi
  return 0
}

_prompt_zle_line_init() {
  emulate -L zsh
  echo "LINEINIT" >> /tmp/zle_markers
}
zle -N zle-line-init _prompt_zle_line_init

_prompt_zle_line_pre_redraw() {
  emulate -L zsh
  echo "PREREDRAW" >> /tmp/zle_markers
}
zle -N zle-line-pre-redraw _prompt_zle_line_pre_redraw

_prompt_precmd() {
  emulate -L zsh
  echo "PRECMD" >> /tmp/zle_markers
}
precmd_functions+=(_prompt_precmd)
