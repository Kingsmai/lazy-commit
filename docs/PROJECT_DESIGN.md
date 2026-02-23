# Project Design: lazy-commit

## 1. Product Goal

Build an intelligent CLI that understands Git changes first, then generates a normalized commit message, and supports one-command apply/push.

Core user value:

- Reduce manual commit writing time.
- Keep commit style consistent (Conventional Commits).
- Preserve human control with preview + confirmation.

## 2. User-Configurable Inputs

The tool is centered around these environment variables:

- `LAZY_COMMIT_MAX_CONTEXT_SIZE`
- `LAZY_COMMIT_API_KEY`
- `LAZY_COMMIT_BASE_URL`
- `LAZY_COMMIT_OPENAI_MODEL_NAME`

CLI flags can override all of them at runtime.

## 3. End-to-End Workflow

1. Detect Git repository and collect change data.
2. Build bounded context from:
   - branch name
   - changed files
   - status
   - staged diff
   - unstaged diff
   - untracked files
   - recent commit subjects
3. Send prompt to LLM provider (OpenAI or Gemini).
4. Require JSON output with strict schema.
5. Normalize and validate:
   - fallback unknown type to `chore`
   - normalize scope/subject/body
   - enforce header width and format
6. Show preview.
7. Optional:
   - stage all
   - commit
   - push
8. Auto-copy generated message to clipboard (unless disabled).

## 4. Architecture

Code modules:

- `src/lazy_commit/config.py`
  - load env/CLI config
  - infer provider
- `src/lazy_commit/git_ops.py`
  - Git read/write operations
- `src/lazy_commit/prompting.py`
  - build system/user prompt
  - trim context by size
- `src/lazy_commit/llm.py`
  - provider abstraction
  - OpenAI + Gemini API paths
- `src/lazy_commit/commit_message.py`
  - parse model JSON output
  - normalize to Conventional Commit message
- `src/lazy_commit/clipboard.py`
  - cross-platform clipboard command fallback
  - auto-copy generated message
- `src/lazy_commit/ui.py`
  - consistent, readable terminal rendering
- `src/lazy_commit/cli.py`
  - command orchestration

## 5. Provider Strategy

Provider is inferred automatically:

- If `LAZY_COMMIT_BASE_URL` includes `generativelanguage.googleapis.com`, use Gemini.
- If model name starts with `gemini`, use Gemini.
- Otherwise use OpenAI-style endpoint.

This keeps setup simple while still supporting both APIs.

## 6. Reliability and Safety

- If no changes exist, exit cleanly.
- `--push` requires `--apply`.
- Commit only runs when staged changes exist (or user passes `--stage-all`).
- Interactive confirmation before commit unless `--yes`.
- Explicit error types for config/git/model failures.

## 7. Extensibility

Planned extension points:

- Add extra providers by implementing a new client method in `llm.py`.
- Add policy profiles (strict conventional, Jira-linked, mono-repo scope policy).
- Add batch mode (`--all-repos`) and pre-commit hooks.
- Add fallback model chain when primary provider fails.
