# Probe: log _prompt_git_untracked value at each precmd
source ~/.zshrc 2>/dev/null || true
# Override _prompt_precmd to log
functions[_prompt_orig_precmd]=$functions[_prompt_precmd]
_prompt_precmd() {
  _prompt_orig_precmd "$@"
  local -i ut=${_prompt_git_untracked:-0}
  local -i us=${_prompt_git_unstaged:-0}
  local -i st=${_prompt_git_staged:-0}
  local -i sh=${_prompt_git_stashed:-0}
  local rc="${_prompt_rh_colors[*]}"
  echo "precmd: untracked=$ut unstaged=$us staged=$st stashed=$sh colors=($rc) rendering=$_prompt_rendering counter=$_prompt_async_counter" >> /tmp/probe_log.txt
}
