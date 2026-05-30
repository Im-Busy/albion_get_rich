---
description: Sync curated files from the private development repo to the public-facing repo. Merges main→public, runs safety checks, strips private data, and pushes only the clean public branch.
---

# Repo Sync — Private → Public Curation

Syncs the `public` branch with the latest `main` changes, automatically stripping private data (IDE configs, test files, npm artifacts, workspace files).

## Usage

```
/repo-sync              # Full sync: merge main → public → push
/repo-sync check        # Safety check only: verify no private files on public branch
/repo-sync status       # Show current branch state and remote config
```

## What It Does

| Step | Action |
|------|--------|
| 1. Verify | Confirm `origin`→private, `public`→public remotes |
| 2. Pull | Fetch latest `main` from private remote |
| 3. Merge | Merge `main` into `public` branch |
| 4. Safety check | Scan for leaked private files (.vscode, test_*.py, npm artifacts, workspace) |
| 5. Clean | If leak detected: `git rm --cached` private files |
| 6. Push | Push clean `public` branch to public repo |
| 7. Return | Switch back to `main` |

## Safety Guarantees

- Only pushes the `public` branch — never `main`
- Detects and strips: `.vscode/`, `albion_get_rich.code-workspace`, `CLI_TOOLS_GUIDE.md`, `test_*.py`, `.kilo/package*`, `.kilo/bun.lock`, `.kilo/node_modules/`, `.kilo/agent-manager.json`, `.kilo/worktrees/`
- Verifies no `main`/`master` branch exists on the public remote after push
- All operations are revertible (no destructive commands)

## Emergency

If private files ever appear on the public repo:
```bash
git push public --delete main 2>$null   # Delete main if it exists
git push public --force public           # Force-push clean public branch
```
