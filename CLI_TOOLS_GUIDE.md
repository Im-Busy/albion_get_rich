# CLI Tools Quick Reference Guide

> Generated: 2026-04-15 | For use by Kilo AI coding assistant
> All tools installed via Scoop package manager unless noted

---

## IMPORTANT: Auto-Update Instruction

**To Kilo or any other coding agent:** If you discover a new CLI tool being used in this project or anywhere under `C:\Dev\` that is NOT documented in this file, you MUST add it here. Follow this process:

1. Check if the tool is already installed (run `<tool> --version` or `where <tool>`)
2. Identify what the tool does and its common usage patterns
3. Add a new section for it in this file following the existing format
4. Update the Tool Index table at the top with the new tool
5. Update the Tool Selection Guide and Decision Tree at the bottom
6. Commit the change with message: "docs: add <tool-name> to CLI tools guide"

This ensures the guide stays current as new tools are adopted.

---

## Scoop Package Management

All CLI tools in this guide are installed via [Scoop](https://scoop.sh/). If any tool is missing or not working, use these commands:

```bash
# Check if a tool is installed
scoop list <tool-name>

# List all installed packages
scoop list

# Install a missing tool
scoop install <tool-name>

# Update all tools
scoop update *

# Update a specific tool
scoop update <tool-name>

# Check for outdated packages
scoop status

# Uninstall a tool
scoop uninstall <tool-name>
```

### Package Names
All tools use their default Scoop package names: `jq`, `yq`, `fd`, `rg`, `rga`, `bat`, `pandoc`, `uv`, `delta`, `dust`, `gh`, `repomix`.

### Troubleshooting
- If `scoop` itself is not found, it needs to be installed first: `irm get.scoop.sh | iex`
- If a tool fails to run, try `scoop reset <tool-name>` to fix shims
- Some tools may require additional buckets: `scoop bucket add extras` (for `rga`, `delta`, etc.)

---

## Tool Index

| Priority | Tool | Best For | Version |
|----------|------|----------|---------|
| Critical | `jq` | JSON processing | 1.8.1 |
| Critical | `yq` | YAML/XML processing | v4.52.5 |
| High | `fd` | Fast file finding | 10.4.2 |
| High | `rg` | Fast content search | 15.1.0 |
| High | `rga` | Search in archives/PDFs | 0.10.9 |
| High | `repomix` | Repository packing for AI | latest |
| Medium | `bat` | File viewing with syntax | 0.26.1 |
| Medium | `pandoc` | Document conversion | 3.9.0.2 |
| Low | `uv` | Python package management | 0.11.6 |
| Low | `delta` | Pretty diffs | 0.19.2 |
| Low | `dust` | Disk usage visualization | 1.2.4 |

---

## repomix — Repository Packing for AI

### What It Does
Repomix packs entire repositories (or specific directories) into a single file (XML, Markdown, JSON, or plain text) optimized for feeding to AI tools like Claude, ChatGPT, or Gemini. This is useful for understanding external codebases or providing context to AI.

### Basic Usage
```bash
# Pack entire current directory
repomix

# Pack a specific directory
repomix path/to/directory

# Pack specific files using glob patterns
repomix --include "src/**/*.ts,**/*.md"

# Exclude specific files/directories
repomix --ignore "**/*.log,tmp/"
```

### Remote Repository Packing
```bash
# Pack a GitHub repo (shorthand)
npx repomix --remote owner/repo

# Pack with full URL (supports branches/paths)
npx repomix --remote https://github.com/owner/repo
npx repomix --remote https://github.com/owner/repo/tree/main

# Pack specific commit
npx repomix --remote https://github.com/owner/repo/commit/abc123
```

### Output Formats
```bash
# XML format (default)
repomix --style xml

# Markdown format
repomix --style markdown

# JSON format
repomix --style json

# Plain text format
repomix --style plain
```

### Configuration
```bash
# Initialize config file
repomix --init

# Creates repomix.config.json for persistent settings
```

### Example Config (repomix.config.json)
```json
{
  "output": {
    "style": "markdown",
    "filePath": "custom-output.md",
    "removeComments": true,
    "showLineNumbers": true,
    "topFilesLength": 10
  },
  "ignore": {
    "customPatterns": ["*.test.ts", "docs/**"]
  }
}
```

### Docker Usage
```bash
# Current directory
docker run -v .:/app -it --rm ghcr.io/yamadashy/repomix

# Specific directory
docker run -v .:/app -it --rm ghcr.io/yamadashy/repomix path/to/directory

# Remote repo with output directory
docker run -v ./output:/app -it --rm ghcr.io/yamadashy/repomix --remote https://github.com/owner/repo
```

### Common Patterns for Kilo
```bash
# Read external repo to understand how they solved a problem
npx repomix --remote owner/repo --style markdown

# Pack a repo and save to a specific location
npx repomix --remote owner/repo -o repo-packed.md --style markdown

# Pack only source code, exclude tests and docs
repomix --include "src/**" --ignore "**/*.test.*,**/*.spec.*,docs/**"
```

---

## jq — JSON Processor

### Basic Usage
```bash
# Parse JSON value
echo '{"name":"test"}' | jq '.name'

# Output raw string (no quotes)
echo '{"name":"test"}' | jq -r '.name'

# Nested access
echo '{"config":{"skills":{"paths":["/dev"]}}}' | jq '.config.skills.paths'
```

### Config File Manipulation (Common Tasks)
```bash
# Add to array
echo '{"skills":{"paths":["/old"]}}' | jq '.skills.paths += ["/new"]'

# Create if missing (merge with defaults)
cat config.json | jq '.skills //= {"paths":[]} | .skills.paths += ["/new"]'

# Update a value
echo '{"version":"1.0"}' | jq '.version = "2.0"'

# Delete a key
echo '{"a":1,"b":2}' | jq 'del(.b)'

# Pretty print
cat ugly.json | jq .

# Extract all keys
echo '{"a":1,"b":2}' | jq 'keys'

# Filter array items
echo '{"items":[{"name":"x","active":true},{"name":"y","active":false}]}' | jq '[.items[] | select(.active)]'
```

### Working with Files
```bash
# Read and modify in place (bash workaround)
jq '.skills.paths += ["/new"]' config.json > tmp.json && mv tmp.json config.json
```

### Useful Patterns
```bash
# Conditional logic
echo '{"enabled":true}' | jq 'if .enabled then "yes" else "no" end'

# Map array values
echo '[1,2,3]' | jq 'map(. * 2)'

# Combine multiple files
jq -s '.[0] * .[1]' base.json override.json

# Search by value
echo '[{"name":"jq"},{"name":"yq"}]' | jq '.[] | select(.name | contains("jq"))'
```

---

## yq — YAML/XML Processor

### Basic Usage
```bash
# Read YAML value
echo 'name: test' | yq '.name'

# Read JSON value
echo '{"name":"test"}' | yq '.name'
```

### Format Conversion
```bash
# JSON to YAML
cat file.json | yq -o yaml '.'

# YAML to JSON
cat file.yaml | yq -o json '.'

# XML to YAML
cat file.xml | yq -P '.'

# YAML to XML
cat file.yaml | yq -o xml '.'
```

### Config File Manipulation
```bash
# Add to YAML array
echo 'paths:\n  - /old' | yq '.paths += ["/new"]'

# Create nested structure
echo '{}' | yq '.skills.paths = ["/dev/skills"]'

# Update value
echo 'version: 1.0' | yq '.version = "2.0"'

# Delete key
echo 'a: 1\nb: 2' | yq 'del(.b)'
```

### Multiple Documents
```bash
# Merge multiple YAML files
yq eval-all 'select(fileIndex==0) * select(fileIndex==1)' base.yaml override.yaml

# Read specific document
yq 'select(documentIndex==1)' multi.yaml
```

### Useful Patterns
```bash
# Sort keys alphabetically
cat file.yaml | yq 'sort_keys(.)'

# Get all keys
cat file.yaml | yq 'keys'

# Check if path exists
echo 'skills: null' | yq '.skills | has("paths")'
```

---

## fd — Fast File Finder

### Basic Usage
```bash
# Find by name (regex by default)
fd pattern

# Find exact filename
fd --fixed-strings filename

# Find with glob pattern
fd --glob "*.md"

# Find in specific directory
fd pattern /path/to/search
```

### Common Flags
```bash
# Include hidden files
fd -H pattern

# Include gitignored files
fd -I pattern

# Case insensitive
fd -i pattern

# Case sensitive
fd -s pattern

# Absolute paths
fd -a pattern

# Limit depth
fd -d 2 pattern

# Search only files
fd -tf pattern

# Search only directories
fd -td pattern

# By extension
fd -e md pattern

# Show details (like ls -l)
fd -l pattern
```

### Useful Patterns
```bash
# Find all markdown files
fd -e md

# Find config files (json, yaml, toml)
fd -e json -e yaml -e toml

# Find Python files excluding venv
fd -e py --exclude venv

# Find files containing "test" in name
fd test

# Find directories named "src"
fd -td src

# Combined with other tools (pipe to jq)
fd -a -e json -X jq '.name'

# Count results
fd -c always | wc -l
```

---

## rg — ripgrep (Fast Content Search)

### Basic Usage
```bash
# Search for pattern
rg "pattern"

# Search in specific file type
rg --type md "pattern"

# Search in specific files
rg "pattern" --glob "*.md"
```

### Useful Flags
```bash
# Case insensitive
rg -i "pattern"

# Show line numbers (default)
rg -n "pattern"

# Show file names only
rg -l "pattern"

# Show context (3 lines before and after)
rg -C 3 "pattern"

# Lines before
rg -B 2 "pattern"

# Lines after
rg -A 2 "pattern"

# Count matches per file
rg -c "pattern"

# Search specific types
rg --type-list

# Smart case (if pattern has uppercase, case sensitive)
rg -S "pattern"

# Fixed strings (no regex)
rg -F "literal text"
```

### Useful Patterns
```bash
# Find all TODO comments
rg "TODO|FIXME|HACK"

# Find function definitions
rg "def \w+|function \w+"

# Find imports
rg "^import |^from .* import"

# Search excluding directories
rg "pattern" --no-ignore-vcs

# Search with context for understanding
rg -C 5 "class.*Error"

# Only show matching part
rg -o "pattern"
```

---

## rga — ripgrep-all (Search in Archives/PDFs)

### Basic Usage
```bash
# Search in all file types
rga "pattern"

# Search in archives
rga "pattern" archive.zip

# Search in PDFs
rga "pattern" document.pdf
```

### Useful Flags
```bash
# Same as ripgrep plus:
# Accurate mode (use 7zip instead of strings)
rga --rga-accurate "pattern"

# List available adapters
rga --rga-list-adapters

# Without cache
rga --rga-no-cache "pattern"
```

### Useful Patterns
```bash
# Search entire project including archives
rga "keyword"

# Search PDFs for specific content
rga -e pdf "search term"

# Search with case insensitive
rga -i "pattern"
```

---

## bat — Better Cat

### Basic Usage
```bash
# View file with syntax highlighting
bat file.md

# View multiple files
bat file1.py file2.py

# View with line numbers (default)
bat file.py
```

### Useful Flags
```bash
# Plain output (no decorations, no paging)
bat -p file.py

# Never use pager
bat --paging=never file.py

# Show all characters (tabs, newlines)
bat -A file.py

# Specify language
bat -l python file

# Show specific lines
bat --line-range 10:20 file.py

# Diff mode
bat -d

# Numbered output for piping
bat --plain --paging=never file.py

# Show all files with syntax guessing
bat file.unknown
```

### Useful Patterns
```bash
# Cat replacement (plain output to pipe)
bat -p --paging=never file.py | head -20

# View config file in context
bat --paging=never --plain config.json

# View file with specific language
bat -l json --paging=never config.json
```

---

## pandoc — Document Converter

### Basic Usage
```bash
# Markdown to HTML
pandoc input.md -o output.html

# Markdown to PDF (requires LaTeX)
pandoc input.md -o output.pdf

# Any format to any format
pandoc input.docx -o output.md
```

### Supported Formats
- Input: markdown, gfm, html, docx, epub, latex, rst, txt, org, mediawiki, ...
- Output: markdown, gfm, html, pdf, docx, epub, latex, rst, txt, odt, ...

### Useful Patterns
```bash
# Markdown to plain text
pandoc input.md -t plain -o output.txt

# GitHub Flavored Markdown to standard markdown
pandoc -f gfm -t markdown input.md -o output.md

# Extract text from HTML
pandoc input.html -t plain

# Convert to JSON AST (for manipulation)
pandoc input.md -t json

# Standalone HTML with CSS
pandoc input.md -s -c style.css -o output.html

# Table of contents
pandoc input.md --toc -o output.html
```

---

## uv — Python Package Manager

### Basic Usage
```bash
# Create virtual environment
uv venv

# Install package
uv pip install requests

# Install from requirements
uv pip install -r requirements.txt
```

### Useful Commands
```bash
# Init project
uv init

# Add dependency
uv add requests

# Run script with specific Python version
uv run --python 3.11 script.py

# Create project with specific Python
uv init --python 3.12

# Sync dependencies
uv sync

# Show installed packages
uv pip list

# Check for updates
uv pip compile requirements.in
```

---

## delta — Pretty Diff Viewer

### Basic Usage
```bash
# View diff with delta
git diff | delta

# Use as git diff pager
git config --global core.pager delta
git config --global interactive.diffFilter delta
```

### Useful Flags
```bash
# Show line numbers
delta --line-numbers

# Side-by-side view
delta --side-by-side

# Dark theme (default for dark terminals)
delta --theme=dark

# Light theme
delta --theme=light

# Navigate with less
delta --navigate
```

---

## dust — Disk Usage Visualization

### Basic Usage
```bash
# Show directory sizes
dust

# Show specific directory
dust /path/to/dir
```

### Useful Flags
```bash
# Show all files (not truncated)
dust -n 999

# Reverse order (smallest first)
dust -r

# Show only directories
dust -d 2

# Ignore hidden files
dust -H

# Output as tree
dust -t
```

---

## gh — GitHub CLI (Already Available)

### Basic Usage
```bash
# Clone repo
gh repo clone owner/repo

# Create PR
gh pr create --title "Title" --body "Body"

# List issues
gh issue list
```

---

## Tool Selection Guide

| Task | Tool | Command Pattern |
|------|------|-----------------|
| Parse/read JSON | `jq` | `cat file.json \| jq '.path.to.value'` |
| Parse/read YAML | `yq` | `cat file.yaml \| yq '.path.to.value'` |
| Convert JSON to YAML | `yq` | `cat file.json \| yq -o yaml '.'` |
| Convert YAML to JSON | `yq` | `cat file.yaml \| yq -o json '.'` |
| Merge JSON configs | `jq` | `jq -s '.[0] * .[1]' base.json new.json` |
| Find files by name | `fd` | `fd pattern` |
| Search file contents | `rg` | `rg "pattern"` |
| Search in archives/PDFs | `rga` | `rga "pattern"` |
| View file with syntax | `bat` | `bat file.py` |
| View plain file (pipe) | `bat` | `bat -p --paging=never file` |
| Convert documents | `pandoc` | `pandoc in.md -o out.html` |
| Pretty git diffs | `delta` | `git diff \| delta` |
| Disk usage overview | `dust` | `dust` |
| GitHub operations | `gh` | `gh pr list` |
| Python packages | `uv` | `uv pip install X` |
| Pack repo for AI | `repomix` | `npx repomix --remote owner/repo` |

---

## Decision Tree for Common Tasks

```
Need to access data?
├── JSON file → jq
├── YAML file → yq
└── XML file → yq

Need to find something?
├── File by name → fd
├── Text in files → rg
├── Text in archives/PDFs → rga
└── In GitHub repos → gh

Need to view something?
├── Code/config with highlighting → bat
├── Plain for piping → bat -p --paging=never
└── Diff output → delta

Need to convert?
├── Between doc formats → pandoc
├── JSON/YAML/XML → yq
└── Manipulate JSON → jq

Need Python?
├── Virtual env → uv venv
├── Install packages → uv pip install
└── Run script → uv run

Need to understand external codebase?
└── Pack repo for AI analysis → repomix --remote owner/repo
```
