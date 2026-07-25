# Probe: log _prompt_rh_colors and region_highlight at key entry points
source ~/.zshrc 2>/dev/null || true

functions[_prompt_orig_append_footer]=$functions[_prompt_zle_append_footer]
_prompt_zle_append_footer() {
  # Log BEFORE making changes
  local rh_before="${region_highlight[*]}"
  local rc="${_prompt_rh_colors[*]}"
  local pos="${_prompt_rh_positions[*]}"
  
  _prompt_orig_append_footer "$@"
  
  local rh_after="${region_highlight[*]}"
  echo "AF: rh=($rc) pos=($pos) widget=$WIDGET pd='${POSTDISPLAY//\$'\n'/<NL>}' rh_before='$rh_before' rh_after='$rh_after'" >> /tmp/probe_log3.txt
}
