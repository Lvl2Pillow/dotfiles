emulate -L zsh 2>/dev/null
PROMPT='%# '
chpwd() {}

TRAPINT() {
  emulate -L zsh
  if zle; then
    : > /tmp/zle_trapint_flag
  fi
  return 0
}

_prompt_zle_line_init() {
  emulate -L zsh
  : > /tmp/zle_lineinit_flag
}
zle -N zle-line-init _prompt_zle_line_init

_prompt_zle_line_pre_redraw() {
  emulate -L zsh
  : > /tmp/zle_preredraw_flag
}
zle -N zle-line-pre-redraw _prompt_zle_line_pre_redraw

_prompt_precmd() {
  : > /tmp/zle_precmd_flag
}
precmd_functions+=(_prompt_precmd)
