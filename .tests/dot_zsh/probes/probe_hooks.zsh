emulate -L zsh 2>/dev/null
PROMPT='%# '
chpwd() {}

TRAPINT() {
  emulate -L zsh
  if zle; then
    print "TRAPINT"
  fi
  return 0
}

_prompt_zle_line_init() {
  emulate -L zsh
  print "LINEINIT"
}
zle -N zle-line-init _prompt_zle_line_init

_prompt_zle_line_pre_redraw() {
  emulate -L zsh
  print "PREREDRAW"
}
zle -N zle-line-pre-redraw _prompt_zle_line_pre_redraw
