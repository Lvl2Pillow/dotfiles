# Probe: log _prompt_rh_colors at key entry points
source ~/.zshrc 2>/dev/null || true

# Override _prompt_precmd
functions[_prompt_orig_precmd]=$functions[_prompt_precmd]
_prompt_precmd() {
  _prompt_orig_precmd "$@"
  local ut=${_prompt_git_untracked:-0}
  local rc="${_prompt_rh_colors[*]}"
  local br="${_prompt_branch_out}"
  local pd_val="${_prompt:-}"
  echo "precmd: untracked=$ut rh=($rc) branch=$br prompt_len=${#_prompt} counter=$_prompt_async_counter" >> /tmp/probe_log2.txt
}

# Override _prompt_zle_append_footer
functions[_prompt_orig_append_footer]=$functions[_prompt_zle_append_footer]
_prompt_zle_append_footer() {
  local rc="${_prompt_rh_colors[*]}"
  local buflen=${#BUFFER}
  local pd="${POSTDISPLAY}"
  echo "append_footer ENTER: rh=($rc) buflen=$buflen pd_len=${#pd} pd_start=${pd:0:30} widget=$WIDGET" >> /tmp/probe_log2.txt
  
  _prompt_orig_append_footer "$@"
  
  local rc2="${_prompt_rh_colors[*]}"
  local pd2="${POSTDISPLAY}"
  echo "append_footer EXIT: rh=($rc2) pd_len=${#pd2} pd=${pd2:0:60}" >> /tmp/probe_log2.txt
}
