---
name: dual-repo-sync
description: Manages a dual-remote Git architecture where a private development repo syncs curated (non-sensitive) files to a public-facing repo. Handles branch curation, .gitignore management, merge safety checks, and leak prevention for IDE configs, test files, npm artifacts, and workspace files.
license: MIT
metadata:
    skill-author: project
---

# Dual-Repo Sync — Private → Public Curation

## Architecture

```
Private Repo (origin)              Public Repo (public)
  main branch                        public branch
  [all files]                        [curated files only]

  git push origin main               git push public public
       │                                    │
       │  git checkout public               │
       │  git merge main                    │
       │  [safety check]                    │
       │  git push public public            │
       └────────────────────────────────────┘
```

## What Stays Private (ALWAYS excluded)

| File/Dir | Reason |
|----------|--------|
| `.vscode/`, `albion_get_rich.code-workspace` | IDE/workspace settings |
| `CLI_TOOLS_GUIDE.md` | Duplicate of shared skill `skills/cli-tools/` |
| `test_nats.py`, `test_cf_bypass.py`, `test_engine.py` | Test files (test_nats.py has hardcoded credentials) |
| `.kilo/package-lock.json`, `.kilo/package.json`, `.kilo/bun.lock` | npm artifacts |
| `.kilo/node_modules/` | npm dependencies |
| `.kilo/agent-manager.json` | Session state |
| `.kilo/worktrees/` | Worktree state |

## What Goes Public (curated showcase)

| Directory | Files | Purpose |
|-----------|-------|---------|
| Root `.py` files | scanner, route finder, bypass engine, etc. | Source code |
| `data_sources/` | 4 files | Data abstraction layer |
| `web/` | 6 files | FastAPI backend + SPA dashboard |
| `albion_map_pathfinder/` | 4 files | Zone graph construction |
| `project_research/` | 2 files | Anti-cheat analysis |
| `AGENTS.md`, `MEMORY.md`, `IDEAS_AND_PLAN.md` | 3 files | Project docs |
| `kilo.json`, `pyproject.toml`, `uv.lock` | 3 files | Project config |
| `.kilo/plans/` | 2 files | Plan docs |
| `.kilo/skills/` | 2 files | Skill definitions |
| `.gitignore`, `.python-version`, `README.md` | 3 files | Root config |

## Sync Workflow (CRITICAL ORDER)

### Step 1: Prepare
```bash
git checkout main && git pull origin main
```

### Step 2: Merge into public branch
```bash
git checkout public
git merge main
```

### Step 3: SAFETY CHECK
```bash
git diff --name-only public@{1}..public | findstr /R "\.vscode\|code-workspace\|CLI_TOOLS\|test_nats\|test_cf\|test_engine\|package-lock\|package\.json\|bun\.lock\|node_modules\|agent-manager\|worktrees"
```

**If ANY output appears:** Files leaked. Run cleanup:
```bash
git rm --cached -r .vscode/ .kilo/node_modules/ .kilo/worktrees/ 2>$null
git rm --cached albion_get_rich.code-workspace CLI_TOOLS_GUIDE.md test_nats.py test_cf_bypass.py test_engine.py 2>$null
git rm --cached .kilo/package-lock.json .kilo/package.json .kilo/bun.lock .kilo/agent-manager.json 2>$null
git commit -m "curate: remove leaked private files from public merge"
```

### Step 4: Push
```bash
git push public public
```

### Step 5: Return to development
```bash
git checkout main
```

## Leak Prevention Rules

1. **Never** push `main` branch to `public` remote — only push the `public` branch
2. **Always** run the safety check after `git merge main` before pushing
3. **Always** verify `git remote -v` shows `public` pointing to the correct public repo
4. **Never** add new test files with credentials to the public branch

## Emergency: If Private Files Get Pushed to Public

1. Immediately delete the offending branch: `git push public --delete <branch>`
2. OR force-push a clean commit: `git push public --force`
3. Rotate any exposed credentials
4. Review GitHub commit history for the leaked data
