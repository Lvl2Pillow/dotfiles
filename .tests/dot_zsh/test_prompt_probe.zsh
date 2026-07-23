# Prompt probe: POSTDISPLAY + region_highlight via append-footer approach
# Uses direct zle -N (no autosuggestions in test env)

emulate -L zsh 2>/dev/null

PROMPT='%# '
chpwd() {}  # suppress OSC 7 for cleaner test

typeset -g _prompt_footer=""
typeset -g _prompt_footer_dir_len=0
typeset -g _prompt_footer_colors=()

_prompt_precmd() {
  emulate -L zsh
  local dir="${PWD/#$HOME/~}"
  _prompt_footer=">> ${dir}"   # ">> " unique marker for test assertions
  _prompt_footer_colors=("fg=135")
  _prompt_footer_dir_len=${#_prompt_footer}
}
precmd_functions+=(_prompt_precmd)

# accept-line: clear POSTDISPLAY so footer is gone before command runs
_prompt_zle_accept_line() {
  emulate -L zsh
  POSTDISPLAY=
  zle .accept-line
}
zle -N accept-line _prompt_zle_accept_line

_prompt_zle_append_footer() {
  emulate -L zsh
  [[ -z "$_prompt_footer" ]] && return

  # Guard: avoid double-appending the same footer
  if [[ "${POSTDISPLAY}" == *$'\n'"${_prompt_footer}" ]]; then
    return
  fi

  POSTDISPLAY="${POSTDISPLAY}"$'\n'"${_prompt_footer}"

  local -i footer_start=$(( ${#BUFFER} + ${#POSTDISPLAY} - ${#_prompt_footer} ))
  local -i footer_end=$(( footer_start + ${#_prompt_footer} ))
  local -i dir_end=$(( footer_start + _prompt_footer_dir_len ))
  region_highlight=("${footer_start} ${dir_end} bold,${_prompt_footer_colors[1]}")
}

# zle-line-init: ensure footer on new prompts
_prompt_zle_line_init() {
  emulate -L zsh
  _prompt_zle_append_footer
}
zle -N zle-line-init _prompt_zle_line_init

# zle-line-pre-redraw: ensure footer after autosuggestions
_prompt_zle_line_pre_redraw() {
  emulate -L zsh
  _prompt_zle_append_footer
}
zle -N zle-line-pre-redraw _prompt_zle_line_pre_redraw
