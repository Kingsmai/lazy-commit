# lazy-commit

`lazy-commit` is a CLI that:

1. Reads and understands your current Git changes (`status`, `diff`, file list).
2. Calls an LLM to generate a normalized Conventional Commit message.
3. Lets you preview, then apply and optionally push in one command.

## Features

- Git-aware context building with size limit (`LAZY_COMMIT_MAX_CONTEXT_SIZE`)
- Unified API config from env vars:
  - `LAZY_COMMIT_API_KEY`
  - `LAZY_COMMIT_BASE_URL`
  - `LAZY_COMMIT_OPENAI_MODEL_NAME`
  - `LAZY_COMMIT_MAX_CONTEXT_SIZE`
- Auto-detect OpenAI vs Gemini API style
- JSON-constrained commit proposal parsing and normalization
- One-command flow for generate -> commit -> push
- Auto-copy generated commit message to clipboard (can disable with `--no-copy`)
- Cleaner CLI output with sectioned summary and message box preview

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Global install (outside venv)

If you already activated a virtual environment, exit first:

```bash
deactivate
```

Install for current user (recommended):

```bash
python3 -m pip install --user .
```

Install in editable mode for current user:

```bash
python3 -m pip install --user -e .
```

Ensure user bin is in `PATH` (zsh):

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Verify:

```bash
lazy-commit --help
```

System-wide install (not recommended) requires `sudo`:

```bash
sudo python3 -m pip install .
```

## Configuration

### OpenAI

```bash
export LAZY_COMMIT_API_KEY="sk-..."
export LAZY_COMMIT_BASE_URL="https://api.openai.com/v1"
export LAZY_COMMIT_OPENAI_MODEL_NAME="gpt-4.1-mini"
export LAZY_COMMIT_MAX_CONTEXT_SIZE="12000"
```

### Gemini

```bash
export LAZY_COMMIT_API_KEY="AIza..."
export LAZY_COMMIT_BASE_URL="https://generativelanguage.googleapis.com/v1beta"
export LAZY_COMMIT_OPENAI_MODEL_NAME="gemini-2.0-flash"
export LAZY_COMMIT_MAX_CONTEXT_SIZE="12000"
```

Notes:

- Provider is auto-detected from `LAZY_COMMIT_BASE_URL` or model name.
- `LAZY_COMMIT_OPENAI_MODEL_NAME` is used as the model ID for both OpenAI and Gemini.
- You can override any value at runtime with CLI flags.

## Usage

Preview only:

```bash
lazy-commit
```

Apply commit with manual confirmation:

```bash
lazy-commit --apply
```

One-click stage + commit + push:

```bash
lazy-commit --apply --stage-all --push --yes
```

Useful flags:

- `--show-context`: print the trimmed context sent to model
- `--show-raw-response`: print raw model response (for debugging)
- `--model`, `--base-url`, `--api-key`, `--max-context-size`: runtime overrides
- `--no-copy`: disable automatic clipboard copy

## Example output

```text
[Generation Summary]
Provider: openai
Model: gpt-4.1-mini
Branch: main
Files: 2
Changed files:
  - src/lazy_commit/cli.py
  - src/lazy_commit/llm.py

[Generated Commit Message]
+-------------------------------------------------------------------+
| feat(cli): add provider-aware one-click commit and push flow      |
|                                                                    |
| Normalize model JSON output and support OpenAI/Gemini behavior.    |
+-------------------------------------------------------------------+
Copied to clipboard via xclip -selection clipboard.
Preview only. Re-run with --apply to create commit.
```

Disable auto-copy:

```bash
lazy-commit --no-copy
```

## Development

Run unit tests:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Project design details:

- `docs/PROJECT_DESIGN.md`
