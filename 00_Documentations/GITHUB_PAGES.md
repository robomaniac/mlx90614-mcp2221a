# Public GitHub repository and Pages

Target: **`robomaniac/mlx90614-mcp2221a`**, public, MIT, branch **`main`**. Site: `https://robomaniac.github.io/mlx90614-mcp2221a/`. See [validation](../05_Data/VALIDATION.md) for the actual publication status. The workflow runs syntax/simulated checks and packages only active `mlx.html` as `index.html`; docs, ZIPs and historical snapshots are not site assets.

These steps are for initial publication or maintenance. **Skip creation/login steps already completed.** Do not recreate a repository, overwrite another remote or repeat login if the correct account is already authenticated. Git and GitHub CLI are publishing tools; neither is required to use the website.

## Prerequisites and authentication

1. Open **VS Code > Terminal > New Terminal > PowerShell**, at this checkout's root. Run in the same terminal:

   ```powershell
   Set-Location -LiteralPath 'C:\Nextcloud\01_Projects\2026-013_MLX90614-WebHID'
   git --version
   Set-Alias -Name gh -Value (Resolve-Path -LiteralPath .\.local\bin\gh.exe).Path
   gh --version
   ```

   The portable official GitHub CLI downloaded during setup is local-only under `.local/bin/gh.exe`. It is not distributed in Git. In another checkout with an installed `gh`, omit the alias. If absent, optionally install it in PowerShell with `winget install --id GitHub.cli --exact --source winget`, then open a new terminal and set the working directory again. Install Git if `git --version` fails before proceeding.

2. **For this prepared local checkout**, the ignored `.local/gh_command.py` helper can reuse the existing Windows Git credential without a new CLI login. It verifies the account is robomaniac and passes the credential only in memory. First check:

   ```powershell
   python .\.local\gh_command.py api user --jq .login
   ```

   Expect `robomaniac`. If it succeeds, replace each `gh` command in this guide with `python .\.local\gh_command.py`, in the same root terminal. For example, `gh repo view ...` becomes `python .\.local\gh_command.py repo view ...`. Do not repeat login in that case. The helper is local-only and is absent from fresh clones. If the helper or credential is unavailable, use ordinary CLI authentication below.

   Check the CLI account:

   ```powershell
   gh auth status --hostname github.com
   gh api user --jq .login
   ```

   The login must be **`robomaniac`**. If already correct, reuse it. If the desired account is already stored but inactive, use `gh auth switch --hostname github.com --user robomaniac` and repeat the login check. If unauthenticated, run:

   ```powershell
   gh auth login --hostname github.com --git-protocol https --web
   ```

   Follow the terminal's device-code/browser instructions while signed into **robomaniac**, then rerun `gh api user --jq .login`. Stop if it returns a different owner. Do not paste tokens or recovery codes into chat or repository files. GitHub CLI stores login outside this project.

## Review and initial publication

1. From the same PowerShell terminal, run the checks and review the files:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\08_Software\mlx90614-webhid\tools\Check-Html.ps1 -Diagnostics
   git status --short --untracked-files=all
   ```

   If this is a new clone/setup without a repository, initialize it **once** using `git init -b main`. The original migration already initializes its working copy. Use a GitHub noreply author identity to avoid publishing a private email. For the robomaniac account verified during setup:

   ```powershell
   git config --local user.name robomaniac
   git config --local user.email 5814871+robomaniac@users.noreply.github.com
   ```

2. Stage the explicit curated paths; inspect every staged change for credentials, private URLs, personal filesystem paths and confidential logs:

   ```powershell
   git add -- README.md AGENTS.md LICENSE .gitignore .gitattributes .github/workflows/pages.yml .vscode/tasks.json 00_Documentations 04_Media 05_Data 08_Software/mlx90614-webhid 99_Archive/webhid-history
   git diff --cached --check
   git diff --cached --stat
   git ls-files
   git diff --cached
   ```

   Confirm no tracked `.env`, secret/key, `.local`, ZIP, complete original backup, legacy Python/prototype or browser-profile files. Archived HTML history is deliberately public. The selected logs and image were reviewed during migration; review new replacements again. Stop and remove sensitive staged files with `git restore --staged -- <exact-file-path>` before committing.

3. Commit only if changes are staged:

   ```powershell
   git commit -m "Prepare MLX90614 MCP2221A monitor for local use and GitHub Pages"
   git branch --show-current
   git remote -v
   ```

   The branch must be `main`. The original migration creates an initial commit; skip a duplicate commit if there are no changes. If `origin` already exists, verify it points to the target repository and do not overwrite another remote.

4. If the target repository does not exist, create/push it:

   ```powershell
   gh repo create robomaniac/mlx90614-mcp2221a --public --source . --remote origin --push --description "Single-file WebHID MLX90614 temperature monitor via MCP2221A USB/I2C bridge"
   ```

   If it already exists with the intended source, use `git push -u origin main` instead. Stop on an authentication, conflict or unexpected-owner error; do not force-push. Verify public visibility:

   ```powershell
   gh repo view robomaniac/mlx90614-mcp2221a --json nameWithOwner,visibility,defaultBranchRef,url
   ```

## Enable and verify Pages

1. In **GitHub > robomaniac/mlx90614-mcp2221a > Settings > Pages > Build and deployment > Source**, select **GitHub Actions**. Alternatively, from the same authenticated terminal, for a repository without Pages yet:

   ```powershell
   gh api --method POST repos/robomaniac/mlx90614-mcp2221a/pages -f build_type=workflow
   ```

   If Pages is already enabled, inspect with `gh api repos/robomaniac/mlx90614-mcp2221a/pages` and use `gh api --method PUT repos/robomaniac/mlx90614-mcp2221a/pages -f build_type=workflow` only when switching its build type is necessary. The site's HTTPS origin provides WebHID's required secure context.

2. Trigger the prepared workflow if there is no successful run yet:

   ```powershell
   gh workflow run pages.yml --repo robomaniac/mlx90614-mcp2221a --ref main
   gh run list --repo robomaniac/mlx90614-mcp2221a --workflow pages.yml --limit 5
   ```

   Copy the newest run's numeric ID from that list into the prompt below:

   ```powershell
   $pagesRunId = Read-Host 'Enter the newest Pages run ID from the list above'
   gh run watch $pagesRunId --repo robomaniac/mlx90614-mcp2221a --exit-status
   ```

   Expect both **validate-and-package** and **deploy** to succeed. Stop on failure; inspect **GitHub > Actions > failed run > failed step** rather than declaring the site deployed.

3. Open **Chrome/Edge** at `https://robomaniac.github.io/mlx90614-mcp2221a/`. Expect the same dark app, secure context and WebHID available. Follow the [operation guide](../08_Software/mlx90614-webhid/README.md#local-setup-and-operation) from the device-connect step. This new origin may ask for fresh device permission.

4. Verify deployed bytes in the same PowerShell terminal, using ignored temporary storage:

   ```powershell
   New-Item -ItemType Directory -Force -Path .\.local | Out-Null
   Invoke-WebRequest -UseBasicParsing -Uri 'https://robomaniac.github.io/mlx90614-mcp2221a/' -OutFile .\.local\deployed-index.html
   Get-FileHash -Algorithm SHA256 -LiteralPath .\.local\deployed-index.html
   Get-FileHash -Algorithm SHA256 -LiteralPath .\08_Software\mlx90614-webhid\mlx.html
   ```

   Both hashes must match after the intended commit finishes deployment. If they differ, check the successful run's commit, browser cache and CDN delay. A byte match validates delivery, not USB sensor operation. Remove the temporary copy with `Remove-Item -LiteralPath .\.local\deployed-index.html` after checking.

## Later updates and rollback

1. Reuse the existing authenticated account/remote and correct local server. Save the HTML, disconnect/reload/reconnect for local testing, then repeat checks and stage/review only intended changes. Inspect `git diff --cached` before pushing.
2. Commit and push to `main` with a descriptive message. The push automatically runs Pages; use the run-list/watch commands above. There is no HTML build step on your computer and no need to repeat repository creation or authentication.
3. To roll back a published change without rewriting history, in PowerShell at the root run `git log --oneline -5`, then:

   ```powershell
   $rollbackCommit = Read-Host 'Enter the complete commit hash to revert from git log'
   git revert $rollbackCommit
   git push origin main
   ```

   Resolve any reported conflicts before pushing. Verify the new deployment and reload the disconnected browser. For an unpublished A/B comparison, use the baseline-copy procedure in the app guide; never edit historical snapshots.

Reference: [GitHub custom Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages). The workflow grants deployment permissions only to the deploy job and includes no secret/token in source.
