# Repository Guidelines

## Project Structure & Module Organization
- `src/lazy_commit/` contains the CLI and core modules:
  - `cli.py` (entrypoint and command flow)
  - `git_ops.py`, `llm.py`, `prompting.py`, `commit_message.py` (core behavior)
  - `config.py`, `ui.py`, `clipboard.py`, `errors.py` (support modules)
- `tests/` holds unit tests (`test_*.py`) by feature area.
- `docs/PROJECT_DESIGN.md` documents workflow and architecture decisions.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate`: create and activate local environment.
- `pip install -e .`: install in editable mode and register the `lazy-commit` CLI.
- `lazy-commit --help`: verify CLI wiring and available flags.
- `python -m unittest discover -s tests -p "test_*.py" -v`: run full unit test suite.
- `python -m unittest tests.test_git_ops -v`: run one test module during iteration.

## Coding Style & Naming Conventions
- Target Python 3.10+ with 4-space indentation and PEP 8 style.
- Prefer explicit type hints (`list[str]`, `-> None`) and keep `from __future__ import annotations` in new modules.
- Use `snake_case` for modules/functions/variables, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants.
- Keep CLI flags consistent with existing long-form kebab-case patterns (for example, `--max-context-size`).
- Keep side effects in orchestration layers (`cli.py`, `git_ops.py`) and parsing/normalization deterministic.

## Testing Guidelines
- Use the standard library `unittest` framework.
- Name files `test_*.py`, test methods `test_*`, and group related cases in `unittest.TestCase` classes.
- Add regression tests for bug fixes, especially for parsing, git edge cases, and provider handling.
- Run the full suite before opening a PR.

## Commit & Pull Request Guidelines
- Follow Conventional Commits, as used in project history: `feat(cli): ...`, `fix(git): ...`, `docs: ...`.
- Keep commit subjects short, imperative, and specific to one logical change.
- PRs should include:
  - concise summary of behavior changes
  - linked issue/task (if available)
  - test evidence (command + result)
  - CLI output snippet when terminal UX changes

## Versioning Rules
- Package version source is `src/lazy_commit/__init__.py` via `__version__`.
- When releasing, update `src/lazy_commit/__init__.py` and `pyproject.toml` `project.version` in the same PR; keep them identical.
- Use semantic versioning:
  - `patch` (`0.1.1`) for bug fixes/refactors without behavior break
  - `minor` (`0.2.0`) for backward-compatible features/flags
  - `major` (`1.0.0`) for breaking CLI/API/config changes
- Do not bump version for docs-only or test-only changes.

## Security & Configuration Tips
- Never commit real API keys or tokens.
- Use environment variables (`LAZY_COMMIT_API_KEY`, `LAZY_COMMIT_BASE_URL`, `LAZY_COMMIT_OPENAI_MODEL_NAME`) for local configuration.
- Use placeholder values in docs and examples.
