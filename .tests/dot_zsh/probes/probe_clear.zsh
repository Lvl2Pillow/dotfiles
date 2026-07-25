emulate -L zsh 2>/dev/null
PROMPT='%# '
chpwd() {}

TRAPINT() {
  emulate -L zsh
  if zle; then
    print $'\033[H\033[2JTRAPINT_CLEAR'
  fi
  return 0
}
