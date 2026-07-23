# Probe: POSTDISPLAY + region_highlight footer. TRAPINT clears below cursor.
# Widget clears POSTDISPLAY, handles break, redraws.

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

TRAPINT() {
  emulate -L zsh
  if zle; then
    # Clear footer line, move up 2 to neutralize zle's \033[1B and gap
    printf '\033[1B\033[2K\033[2A'
    return $(( 128 + $1 ))
  fi
  return 0
}

# accept-line: clear POSTDISPLAY so footer is gone before command runs
_prompt_zle_accept_line() {
  emulate -L zsh
  POSTDISPLAY=
  zle .accept-line
}
zle -N accept-line _prompt_zle_accept_line

_prompt_zle_ctrlc() {
  emulate -L zsh
  POSTDISPLAY=
  zle .send-break
  zle .reset-prompt
}
zle -N _prompt_zle_ctrlc
bindkey '^C' _prompt_zle_ctrlc

_prompt_zle_append_footer() {
  emulate -L zsh
  [[ -z "$_prompt_footer" ]] && return
  if [[ "$POSTDISPLAY" == *$'\n'"${_prompt_footer}" ]]; then
    return
  fi
  POSTDISPLAY="${POSTDISPLAY}"$'\n'"${_prompt_footer}"
  local -i footer_start=$(( ${#BUFFER} + ${#POSTDISPLAY} - ${#_prompt_footer} ))
  local -i footer_end=$(( footer_start + ${#_prompt_footer} ))
  local -i dir_end=$(( footer_start + _prompt_footer_dir_len ))
  region_highlight=("${footer_start} ${dir_end} bold,${_prompt_footer_colors[1]}")
}

_prompt_zle_line_init() {
  emulate -L zsh
  _prompt_zle_append_footer
}
zle -N zle-line-init _prompt_zle_line_init

_prompt_zle_line_pre_redraw() {
  emulate -L zsh
  _prompt_zle_append_footer
}
zle -N zle-line-pre-redraw _prompt_zle_line_pre_redraw
