# Probe: does print work from TRAPINT?

emulate -L zsh 2>/dev/null
PROMPT='%# '
chpwd() {}

TRAPINT() {
  emulate -L zsh
  # Print unique marker to see if output works from TRAPINT
  print "TRAPINT_MARKER"
  return 0  # default handling
}

_prompt_zle_send_break() {
  emulate -L zsh
  print "SEND_BREAK_MARKER"
  POSTDISPLAY=
  zle .send-break
  print "SEND_BREAK_AFTER"
  zle -R
}
zle -N send-break _prompt_zle_send_break
