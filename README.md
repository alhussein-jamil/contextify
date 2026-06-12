# contextify

Export any git repository into a **single compressed context bundle** for LLMs, code review, or archival.

```
context_export/
├── context.txt       # tree + index + raw source (compact format)
├── assets/           # binary files, mirroring original paths
├── statistics.json   # tokens, languages, per-file manifest
└── statistics.txt    # human-readable summary
```

## Install

### Binary (recommended) — no Python required

The release zip is a **fully standalone executable** (Python, rich, and the ignore
template are bundled). Unzip and run — nothing else to install.

Download from [GitHub Releases](https://github.com/alhussein-jamil/contextify/releases) (not the **Packages** tab — that is for container/npm registries; binaries ship as release assets):

| Platform | Archive |
|----------|---------|
| Linux x86_64 | `contextify-<version>-linux-x86_64.zip` |
| Windows x86_64 | `contextify-<version>-windows-x86_64.zip` |

```bash
unzip contextify-*-linux-x86_64.zip
cd contextify-*-linux-x86_64
./contextify --help
./contextify /path/to/repo

# optional: install to ~/.local/bin
./install.sh
```

```powershell
# Windows
Expand-Archive contextify-*-windows-x86_64.zip
.\contextify.exe --help
```

Verify: `sha256sum -c SHA256SUMS` (Linux) using checksums from the release page.

### pip / uv (developers)

```bash
uv pip install contextify
# optional extras
uv pip install "contextify[all]"   # rich + tiktoken
```

### From source

```bash
git clone https://github.com/alhussein-jamil/contextify.git
cd contextify
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,all]"
contextify --help
```

## Usage

```bash
# export a repo → ./context_export/ in your current directory (not inside the repo)
contextify /path/to/repo
contextify .   # when run from inside a repo, writes ./context_export/ here

# custom output folder
contextify /path/to/repo -o ./my_bundle

# verbose logging
contextify . -v

# honour .gitignore in addition to .contextifyignore
contextify . --no-gitignore   # include gitignored files

# custom ignore rules file
contextify . --ignore-file ./.contextifyignore
```

### Skip rules — `.contextifyignore`

Skip patterns use **gitignore syntax**. Add a `.contextifyignore` in your repo root, or contextify falls back to its bundled template.

```gitignore
# never re-export previous runs
context_export/
*_export/

# locks & generated noise
*.lock
node_modules/
dist/
*.min.js
```

The active export directory is **always** excluded automatically, even if omitted from the ignore file.

### Output format

`context.txt` is optimised for size:

1. **TREE** — ASCII directory layout
2. **INDEX** — tab-separated `path`, `start`, `end`, `kind`, `lang`, `tokens`
3. **CONTENTS** — each file under a `=== path/to/file ===` header, then raw source

Search for `=== src/main.py ===` to jump to a file.

## Development

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,all]"
pytest
ruff check src tests
```

### Build standalone binary locally

```bash
# Linux
bash scripts/build_linux.sh
./dist/contextify --help

# Windows (PowerShell)
./scripts/build_windows.ps1
./dist/contextify.exe --help
```

### Cutting a release

**Releases** (permanent download zips) are separate from **CI** (temporary Artifacts on each Actions run) and from **Packages** (unused here).

Bump `version` in `pyproject.toml` **and** `src/contextify/__init__.py`, then either:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Or **Actions → Release → Run workflow** (leave *dry run* unchecked).

That uploads Linux + Windows zips and `SHA256SUMS` to the
[Releases](https://github.com/alhussein-jamil/contextify/releases) page.
Tag must match the package version (`v0.1.0` ↔ `0.1.0`).

## License

MIT — see [LICENSE](LICENSE).
