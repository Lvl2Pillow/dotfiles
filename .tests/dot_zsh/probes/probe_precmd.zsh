# Probe: does precmd fire after SIGINT re-entry?

emulate -L zsh 2>/dev/null
PROMPT='%# '
chpwd() {}

# Track if precmd ran
typeset -g PRECMD_RAN=0

TRAPINT() {
  emulate -L zsh
  if zle; then
    print "TRAPINT_MARKER"
  fi
  return 0
}

_prompt_precmd() {
  PRECMD_RAN=$(( PRECMD_RAN + 1 ))
  print "PRECMD_RAN=$PRECMD_RAN"
}
precmd_functions+=(_prompt_precmd)

_prompt_zle_line_init() {
  emulate -L zsh
  print "LINEINIT_RAN"
}
zle -N zle-line-init _prompt_zle_line_init
