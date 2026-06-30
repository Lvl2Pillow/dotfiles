---
name: browse-git-repo
description: Shallow clone and browse Git repositories locally. Use when inspecting source files beyond just the README.
---

## Instructions

1. Always check if repo has already been cloned into `/tmp/{repo}`. If it exists, skip to step 5.

2. Check repo size via GitHub API:
   ```bash
   curl -s "https://api.github.com/repos/{owner}/{repo}" | grep -o '"size": [0-9]*'
   ```
   (size is in KB)

3. If size > 10240 KB, do NOT clone. Report the limitation. Skip remaining steps.

4. Shallow clone if under threshold:
   ```bash
   git clone --depth 1 https://github.com/{owner}/{repo}.git /tmp/{repo}
   ```

5. Browse with `read`, `glob`, `grep`, `bash: ls` in `/tmp/{repo}`.

6. Do NOT clean up the cloned repo after analysis.
