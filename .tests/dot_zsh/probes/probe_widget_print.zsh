# Probe: does print work from a zle widget?

emulate -L zsh 2>/dev/null
PROMPT='%# '
chpwd() {}

TRAPINT() {
  emulate -L zsh
  if zle; then
    return $(( 128 + $1 ))
  fi
  return 0
}

_prompt_zle_ctrlc() {
  emulate -L zsh
  print "CLEAR_MARKER"
  POSTDISPLAY=
  zle .send-break
  zle .reset-prompt
}
zle -N _prompt_zle_ctrlc
bindkey '^C' _prompt_zle_ctrlc
