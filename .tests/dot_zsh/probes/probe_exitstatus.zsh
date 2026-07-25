# Probe: check $? in zle-line-init after SIGINT
emulate -L zsh 2>/dev/null
PROMPT='%# '
chpwd() {}
typeset -g _prompt_footer=""
typeset -g _prompt_footer_dir_len=0
typeset -g _prompt_footer_colors=()

_prompt_precmd() {
  emulate -L zsh
  local dir="${PWD/#$HOME/~}"
  _prompt_footer=">> ${dir}"
  _prompt_footer_colors=("fg=135")
  _prompt_footer_dir_len=${#_prompt_footer}
}
precmd_functions+=(_prompt_precmd)

_prompt_zle_line_init() {
  emulate -L zsh
  # Print $? to terminal so test can read it
  print -n "EXITSTATUS=$?"
  _prompt_footer=">> ${PWD/#$HOME/~}"
  POSTDISPLAY=$'\n'"${_prompt_footer}"
}

zle -N zle-line-init _prompt_zle_line_init
