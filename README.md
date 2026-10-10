# lazy-commit

`lazy-commit` is a Python CLI that understands your local Git changes, asks an LLM for a structured Conventional Commit proposal, normalizes the result, and optionally runs `git commit` and `git push` in one flow.

Current package version: `0.12.1`.

## Highlights

- Provider-aware generation for OpenAI-compatible APIs and Gemini APIs
- Bounded Git context (`LAZY_COMMIT_MAX_CONTEXT_SIZE`) to control prompt size
- Standalone token counting mode (`--count-tokens`) with model-aware encoding lookup
- Deterministic normalization of commit message fields
- Preview-first workflow with optional apply, stage-all, and push
- WIP mode (`--wip`) that keeps LLM generation and forces commit type to `wip`
- Cross-platform clipboard copy enabled by default (`--no-copy` to disable)
- Built-in multilingual UI (`en`, `zh-CN`, and `zh-TW`)
- JSON locale catalogs with built-in i18n validation (`--check-i18n`)
- Readable terminal UI with Rich rendering and plain-text fallback
- Full-screen TUI mode with file navigation, diff preview, generate/copy/commit actions (`--tui`)

## Requirements

- Python `>=3.10`
- Git available in `PATH`
- A model API key (OpenAI-compatible or Gemini) for commit generation flow

## Installation

### 快捷安装 / Quick install

支持 macOS、Linux、Windows 和 WSL。只需提前安装 Git；安装脚本会自动准备
uv、Python 3.13 和独立的工具环境，并将命令目录加入 PATH。无需管理员权限，
也无需手动激活虚拟环境。首次安装需要联网；安装完成后重新打开终端。

From a checkout (installs your local code, including unpublished changes):

macOS / Linux / WSL:

```bash
sh scripts/install.sh
```

Windows PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install.ps1
```

The scripts reuse uv when available, otherwise download its
[official installer](https://docs.astral.sh/uv/getting-started/installation/).
They install into an isolated environment using Python 3.13 and verify `--version`.
Rerun the same command to update. A wheel, source directory, or Git URL can be
passed as the first argument (`-Source` in PowerShell).

Already have [uv](https://docs.astral.sh/uv/)? Install directly from GitHub,
without cloning or having Python preinstalled (this installs the **published
repository state**, not local changes):

```bash
uv tool install --python 3.13 "git+https://github.com/Kingsmai/lazy-commit.git"
uv tool update-shell
```

These two commands work in both Unix shells and Windows PowerShell. Open a new
terminal, then verify:

```bash
lazy-commit --version
lazy-commit --lang zh-CN --help
```

Update or uninstall an installation managed by uv:

```bash
uv tool upgrade lazy-commit
uv tool uninstall lazy-commit
```

For installs from a local checkout, rerun the installer after updating the code.
`uv tool uninstall` removes the command and its environment; generated history
is retained. If you already use pipx, the equivalent source install is:

```bash
pipx install "git+https://github.com/Kingsmai/lazy-commit.git"
pipx ensurepath
```

### Platform support

| Platform | CLI | Full-screen TUI | Clipboard |
| --- | --- | --- | --- |
| macOS (Apple Silicon / Intel) | Supported | Python curses + interactive terminal | `pbcopy` |
| Linux | Supported | Python curses + interactive terminal | `wl-copy` (Wayland), `xclip`/`xsel` (X11) |
| Windows x64 | Supported | `windows-curses` installed automatically | `clip` (Unicode) |
| WSL | Supported | Linux curses + interactive terminal | `clip.exe`, then Linux tools |
| SSH / headless CI | Supported | Requires an interactive terminal | Optional; use `--no-copy` |

CI is configured to test Python 3.10–3.14 on macOS, Ubuntu, and Windows, including
package installation, CLI entry points, locales, and curses imports. Installer
smoke checks install a built wheel twice on all three platforms. Interactive
terminal behavior and WSL clipboard interop still need validation on real hosts.
Native Windows ARM64 and other architectures depend on available dependency
wheels and are not covered by this CI matrix.

Python 3.14 Windows wheels are available in
[windows-curses 2.4.2](https://pypi.org/project/windows-curses/2.4.2/).
Clipboard tools are optional: if copying is unavailable, the generated message
is still printed. Git must be installed separately and available in PATH.

On Windows, CLI output redirected to a pipe or file uses UTF-8, including help
and error messages. This keeps Chinese text readable in CI and redirected logs.

### Local development install

macOS / Linux / WSL (Python 3.10+):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m lazy_commit --help
```

`python -m lazy_commit` is also available when the console script is not on PATH.

## Quick Start

### 1. Configure environment variables

OpenAI-compatible setup:

```bash
export LAZY_COMMIT_API_KEY="sk-..."
export LAZY_COMMIT_BASE_URL="https://api.openai.com/v1"
export LAZY_COMMIT_OPENAI_MODEL_NAME="gpt-4.1-mini"
export LAZY_COMMIT_MAX_CONTEXT_SIZE="12000"
export LAZY_COMMIT_LANG="en"
```

Gemini setup:

```bash
export LAZY_COMMIT_API_KEY="AIza..."
export LAZY_COMMIT_BASE_URL="https://generativelanguage.googleapis.com/v1beta"
export LAZY_COMMIT_OPENAI_MODEL_NAME="gemini-2.0-flash"
export LAZY_COMMIT_MAX_CONTEXT_SIZE="12000"
export LAZY_COMMIT_LANG="zh-CN"
```

Windows PowerShell configuration (for the current terminal session):

```powershell
$env:LAZY_COMMIT_API_KEY = "your-api-key"
$env:LAZY_COMMIT_BASE_URL = "https://api.openai.com/v1"
$env:LAZY_COMMIT_OPENAI_MODEL_NAME = "gpt-4.1-mini"
$env:LAZY_COMMIT_LANG = "zh-CN"
```

### 2. Generate preview only

```bash
lazy-commit
```

### 3. Apply commit (manual confirmation)

```bash
lazy-commit --apply
```

### 4. One command stage + commit + push (non-interactive)

```bash
lazy-commit --apply --stage-all --push --yes
```

### 5. Count tokens only (no Git/API key required)

```bash
lazy-commit --count-tokens "feat(cli): add token count mode"
echo "你好，世界" | lazy-commit --count-tokens --token-model gpt-4.1-mini
```

### 6. Generate WIP message with LLM (force `wip` type)

```bash
lazy-commit --wip
lazy-commit --wip --apply --stage-all --yes
```

### 7. Launch the full-screen TUI

```bash
lazy-commit --tui
lazy-commit --tui --wip --no-copy
```

If `--tui` reports that TUI mode is unavailable on Windows, rerun the installer to refresh `windows-curses` in the same environment. Use an interactive terminal such as Windows Terminal.

TUI key bindings:

- `Tab`: switch focus between file list, diff preview, and commit message
- `j` / `k` or arrow keys: move selection / scroll focused pane
- `PgUp` / `PgDn`: scroll faster
- `g`: generate commit message
- `y`: copy generated message
- `s`: stage or unstage the selected file
- `a`: stage all changes
- `c`: create commit with current message
- `p`: create commit and push
- `r`: refresh git snapshot
- `q`: quit

## Configuration Reference

Environment variables:

| Variable | Required | Description |
| --- | --- | --- |
| `LAZY_COMMIT_API_KEY` | Yes | API key for OpenAI-compatible or Gemini request |
| `LAZY_COMMIT_BASE_URL` | No | Base URL for API endpoint selection |
| `LAZY_COMMIT_OPENAI_MODEL_NAME` | No | Model id used for both OpenAI-compatible and Gemini modes |
| `LAZY_COMMIT_MAX_CONTEXT_SIZE` | No | Max context size in characters (must be positive integer) |
| `LAZY_COMMIT_MAX_CONTEXT_TOKENS` | No | Max context tokens before compression strategy is applied |
| `LAZY_COMMIT_LANG` | No | UI language (`en` default, `zh-CN`/`zh-TW` supported) |

Compatibility aliases also supported:

- `LAZY_COMMIT_OPENAI_API_KEY` (fallback if `LAZY_COMMIT_API_KEY` is unset)
- `LAZY_COMMIT_OPENAI_BASE_URL` (fallback if `LAZY_COMMIT_BASE_URL` is unset)

CLI flags override environment values at runtime:

- `--api-key`
- `--base-url`
- `--model`
- `--max-context-size`
- `--max-context-tokens`
- `--lang`

## Provider Detection and Defaults

`lazy-commit` infers provider automatically:

1. If base URL contains `generativelanguage.googleapis.com`, provider is Gemini.
2. Else if model name starts with `gemini`, provider is Gemini.
3. Otherwise provider is OpenAI-compatible.

Defaults:

- Default OpenAI-compatible base URL: `https://api.openai.com/v1`
- Default Gemini base URL: `https://generativelanguage.googleapis.com/v1beta`
- Default model when provider is OpenAI-compatible: `gpt-4.1-mini`
- Default model when provider is Gemini: `gemini-3-pro-preview`
- Default max context size: `12000`

OpenAI base URL normalization:

- If you set `https://api.openai.com` (without `/v1`), the CLI automatically normalizes it to `https://api.openai.com/v1`.

## Command Usage

```text
lazy-commit [--api-key API_KEY] [--base-url BASE_URL] [--model MODEL]
            [--max-context-size N] [--max-context-tokens N]
            [--count-tokens [TEXT]]
            [--token-model MODEL] [--token-encoding ENCODING]
            [--lang LANG] [--list-languages] [--check-i18n]
            [--tui]
            [--apply] [--push] [--stage-all] [--yes] [--wip]
            [--remote REMOTE] [--branch BRANCH]
            [--show-context] [--show-raw-response] [--copy | --no-copy]
```

Options:

| Option | Description |
| --- | --- |
| `--version` | Print the installed version and exit |
| `--apply` | Run `git commit` with generated message |
| `--push` | Push after commit (requires `--apply`) |
| `--stage-all` | Stage tracked and untracked changes before commit |
| `--yes` | Skip confirmation prompt when `--apply` is used |
| `--wip` | Keep LLM generation, but force normalized commit type to `wip` |
| `--max-context-tokens` | Token budget for model context; triggers automatic compression when exceeded |
| `--remote` | Remote name for push (default `origin`) |
| `--branch` | Branch name for push (default current branch) |
| `--show-context` | Print trimmed context sent to model |
| `--show-raw-response` | Print raw model response before parsing |
| `--copy` | Enable clipboard copy (default enabled) |
| `--no-copy` | Disable clipboard copy |
| `--count-tokens [TEXT]` | Count tokens for text and exit; omit `TEXT` to read from stdin |
| `--token-model` | Model name used for tokenizer lookup (count mode + generation token estimation) |
| `--token-encoding` | Explicit tokenizer encoding override (for example `o200k_base`) |
| `--lang` | UI language override (for example `en`, `zh-CN`, `zh-TW`) |
| `--list-languages` | Print all supported UI languages and aliases, then exit |
| `--check-i18n` | Validate locale catalogs (missing keys / placeholder mismatch), then exit |
| `--tui` | Launch the full-screen interactive TUI |

When `--count-tokens` is used, the command exits after printing token metadata and does not require Git repository checks or API key configuration.

## Interface Language

`lazy-commit` supports localized CLI text for:

- help/usage output
- progress logs
- section titles and UI labels
- handled error messages
- clipboard status messages

Language resolution order:

1. `--lang` (highest priority)
2. `LAZY_COMMIT_LANG`
3. English (`en`, fallback default)

Supported language values:

- English: `en`, `en-US`, `en-GB`
- Simplified Chinese: `zh`, `zh-CN`, `zh_Hans`, `zh-SG`, `cn`
- Traditional Chinese (Taiwan): `zh-TW`, `zh_Hant`, `zh-Hant`, `zh-Hant-TW`, `zh-HK`, `zh-MO`, `tw`

Examples:

```bash
lazy-commit --lang zh-CN --help
LAZY_COMMIT_LANG=zh-CN lazy-commit --count-tokens "你好"
lazy-commit --lang zh-TW --help
lazy-commit --list-languages
lazy-commit --check-i18n
```

Notes:

- Unknown language values fall back to English.
- In Chinese mode, commit confirmation accepts `是` in addition to `y`/`yes`.
- Locale files live in `src/lazy_commit/locales/*.json`.
- `--check-i18n` reports missing keys and placeholder mismatch issues for translation contributions.
- `python3 scripts/i18n_sync.py --locale zh-CN --locale zh-TW` generates `*.pending.json` templates for untranslated keys.

When generating commits, lazy-commit prints estimated prompt token usage.  
If `--max-context-tokens` (or `LAZY_COMMIT_MAX_CONTEXT_TOKENS`) is set and exceeded, it compresses context in this order:
1. Drop low-priority sections (`Untracked Files`, `Recent Commit Subjects`)
2. Compress large diff sections (`Staged Diff`, `Unstaged Diff`)
3. Hard-truncate remaining context to fit token budget

## Runtime Flow

1. Load settings from env and CLI overrides.
2. Ensure current directory is a Git repository.
3. Collect snapshot:
   - branch
   - status
   - staged diff
   - unstaged diff
   - untracked files
   - changed file list
   - recent commit subjects
4. Build bounded context string.
5. Request a JSON proposal from the model.
6. Parse and normalize to final commit message.
7. Show generation summary, changed files, and message preview.
8. Optionally:
   - copy to clipboard
   - stage all
   - commit
   - push

If there are no local changes, the command exits cleanly after snapshot collection.

When `--wip` is used, lazy-commit still runs the normal LLM flow (context building + model generation),
then forces the normalized commit `type` to `wip` before preview/commit.

## Commit Message Normalization Rules

- Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `wip`, `revert`
- Unknown `type` is normalized to `chore`
- Invalid `scope` is dropped (scope pattern: `[a-zA-Z0-9._/-]+`)
- Subject is whitespace-normalized and trailing `.` is removed
- Header is capped at 72 characters by trimming the subject if needed
- Body lines are wrapped to width 100
- `breaking_change=true` adds a standard `BREAKING CHANGE:` line when missing

## Clipboard Behavior

Clipboard copy is enabled by default.

Command priority by platform:

- Windows: `clip`
- macOS: `pbcopy`
- Linux: `wl-copy`, then `xclip`, then `xsel`
- WSL: prefer `clip.exe`, then Linux commands

If no command is available, generation still succeeds and a warning is shown.

## Exit Codes

- `0`: success (including preview-only and no-changes cases)
- `1`: user canceled at confirmation prompt
- `2`: handled configuration/git/LLM error
- `130`: interrupted by `Ctrl+C`

## Troubleshooting

- `--push requires --apply`:
  - Add `--apply` when using `--push`.
- `No staged changes. Use --stage-all or stage files manually.`:
  - Stage files first or add `--stage-all`.
- HTTP `403` with error code `1010`:
  - Usually means network/WAF blocking or wrong base URL.
  - OpenAI-compatible should use `https://api.openai.com/v1`.
  - Gemini should use `https://generativelanguage.googleapis.com/v1beta`.
- Clipboard warning:
  - Install a clipboard utility for your platform or use `--no-copy`.
- Language did not switch:
  - Prefer explicit `--lang zh-CN` or `--lang zh-TW` to override environment values.
  - Unknown language codes automatically fall back to English.

## Development

Run all tests:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

Run a single module:

```bash
python3 -m unittest tests.test_git_ops -v
```

Architecture details:

- `docs/PROJECT_DESIGN.md`
- `CONTRIBUTING.md`

## Source Layout

- `src/lazy_commit/cli.py`: CLI entrypoint and orchestration
- `src/lazy_commit/config.py`: settings loading and provider detection
- `src/lazy_commit/git_ops.py`: git snapshot/commit/push operations
- `src/lazy_commit/prompting.py`: context and prompt construction
- `src/lazy_commit/llm.py`: provider-specific API calls
- `src/lazy_commit/commit_message.py`: JSON parsing and normalization
- `src/lazy_commit/clipboard.py`: cross-platform clipboard integration
- `src/lazy_commit/i18n.py`: language detection and translation helpers
- `src/lazy_commit/locales/`: locale catalogs (`en.json`, `zh-cn.json`, `zh-tw.json`)
- `src/lazy_commit/ui.py`: terminal rendering helpers

## License

MIT
