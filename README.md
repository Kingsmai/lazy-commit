# lazy-commit

`lazy-commit` is a Python CLI that understands your local Git changes, asks an LLM for a structured Conventional Commit proposal, normalizes the result, and optionally runs `git commit` and `git push` in one flow.

Current package version: `0.3.1`.

## Highlights

- Provider-aware generation for OpenAI-compatible APIs and Gemini APIs
- Bounded Git context (`LAZY_COMMIT_MAX_CONTEXT_SIZE`) to control prompt size
- Deterministic normalization of commit message fields
- Preview-first workflow with optional apply, stage-all, and push
- Cross-platform clipboard copy enabled by default (`--no-copy` to disable)
- Readable terminal UI with Rich rendering and plain-text fallback

## Requirements

- Python `>=3.10`
- Git available in `PATH`
- A model API key (OpenAI-compatible or Gemini)

## Installation

### Local development install (editable)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Verify:

```bash
lazy-commit --help
```

### User-level install (outside venv)

```bash
python3 -m pip install --user .
```

If needed, add `~/.local/bin` to your shell `PATH`:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## Quick Start

### 1. Configure environment variables

OpenAI-compatible setup:

```bash
export LAZY_COMMIT_API_KEY="sk-..."
export LAZY_COMMIT_BASE_URL="https://api.openai.com/v1"
export LAZY_COMMIT_OPENAI_MODEL_NAME="gpt-4.1-mini"
export LAZY_COMMIT_MAX_CONTEXT_SIZE="12000"
```

Gemini setup:

```bash
export LAZY_COMMIT_API_KEY="AIza..."
export LAZY_COMMIT_BASE_URL="https://generativelanguage.googleapis.com/v1beta"
export LAZY_COMMIT_OPENAI_MODEL_NAME="gemini-2.0-flash"
export LAZY_COMMIT_MAX_CONTEXT_SIZE="12000"
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

## Configuration Reference

Environment variables:

| Variable | Required | Description |
| --- | --- | --- |
| `LAZY_COMMIT_API_KEY` | Yes | API key for OpenAI-compatible or Gemini request |
| `LAZY_COMMIT_BASE_URL` | No | Base URL for API endpoint selection |
| `LAZY_COMMIT_OPENAI_MODEL_NAME` | No | Model id used for both OpenAI-compatible and Gemini modes |
| `LAZY_COMMIT_MAX_CONTEXT_SIZE` | No | Max context size in characters (must be positive integer) |

Compatibility aliases also supported:

- `LAZY_COMMIT_OPENAI_API_KEY` (fallback if `LAZY_COMMIT_API_KEY` is unset)
- `LAZY_COMMIT_OPENAI_BASE_URL` (fallback if `LAZY_COMMIT_BASE_URL` is unset)

CLI flags override environment values at runtime:

- `--api-key`
- `--base-url`
- `--model`
- `--max-context-size`

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
            [--max-context-size N] [--apply] [--push] [--stage-all]
            [--yes] [--remote REMOTE] [--branch BRANCH]
            [--show-context] [--show-raw-response] [--copy | --no-copy]
```

Options:

| Option | Description |
| --- | --- |
| `--apply` | Run `git commit` with generated message |
| `--push` | Push after commit (requires `--apply`) |
| `--stage-all` | Stage tracked and untracked changes before commit |
| `--yes` | Skip confirmation prompt when `--apply` is used |
| `--remote` | Remote name for push (default `origin`) |
| `--branch` | Branch name for push (default current branch) |
| `--show-context` | Print trimmed context sent to model |
| `--show-raw-response` | Print raw model response before parsing |
| `--copy` | Enable clipboard copy (default enabled) |
| `--no-copy` | Disable clipboard copy |

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

## Commit Message Normalization Rules

- Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`
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

## Source Layout

- `src/lazy_commit/cli.py`: CLI entrypoint and orchestration
- `src/lazy_commit/config.py`: settings loading and provider detection
- `src/lazy_commit/git_ops.py`: git snapshot/commit/push operations
- `src/lazy_commit/prompting.py`: context and prompt construction
- `src/lazy_commit/llm.py`: provider-specific API calls
- `src/lazy_commit/commit_message.py`: JSON parsing and normalization
- `src/lazy_commit/clipboard.py`: cross-platform clipboard integration
- `src/lazy_commit/ui.py`: terminal rendering helpers

## License

MIT
