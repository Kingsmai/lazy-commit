# Contributing to `lazy-commit`

Thanks for contributing. This guide explains how to propose changes, run the project locally, and prepare high-quality pull requests.

## Ways to Contribute

- Report bugs and edge cases
- Propose feature improvements
- Improve docs and examples
- Submit code fixes or new features

## Development Setup

1. Clone the repository and enter the project directory.
2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install in editable mode:

```bash
pip install -e .
```

4. Verify CLI wiring:

```bash
lazy-commit --help
```

## Project Structure

- `src/lazy_commit/cli.py`: CLI entrypoint and orchestration
- `src/lazy_commit/git_ops.py`: Git read/write operations
- `src/lazy_commit/llm.py`: model/provider API calls
- `src/lazy_commit/prompting.py`: prompt and bounded context construction
- `src/lazy_commit/commit_message.py`: parsing and normalization logic
- `src/lazy_commit/config.py`: environment/CLI config resolution
- `src/lazy_commit/ui.py`: terminal rendering helpers
- `src/lazy_commit/clipboard.py`: clipboard integration
- `src/lazy_commit/errors.py`: typed error definitions
- `src/lazy_commit/i18n.py`: language normalization, translation loading, fallback rules
- `src/lazy_commit/locales/`: editable locale catalogs (`*.json`)
- `tests/`: unit tests by feature area
- `docs/PROJECT_DESIGN.md`: architecture and workflow design notes

## Coding Guidelines

- Target Python `3.10+`.
- Follow PEP 8 and use 4-space indentation.
- Prefer explicit type hints (`list[str]`, `-> None`) in new or modified code.
- Naming conventions:
  - modules/functions/variables: `snake_case`
  - classes: `PascalCase`
  - constants: `UPPER_SNAKE_CASE`
- Keep CLI flags in long-form kebab-case (for example, `--max-context-size`).
- Keep side effects in orchestration layers (`cli.py`, `git_ops.py`) and keep parsing/normalization deterministic.

## Translation (i18n) Contributions

- Edit locale files in `src/lazy_commit/locales/*.json`.
- Keep `en.json` as the baseline key set.
- For non-English locale files:
  - keep the same keys as `en.json`
  - keep placeholder names identical (for example `{model_name}`, `{count}`)
- Run translation health checks:

```bash
lazy-commit --check-i18n
```

- Use this command to inspect discoverable language aliases:

```bash
lazy-commit --list-languages
```

## Testing

This project uses the standard library `unittest`.

Run the full suite before opening a PR:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Run a single test module while iterating:

```bash
python -m unittest tests.test_git_ops -v
```

Test conventions:

- Test files: `test_*.py`
- Test methods: `test_*`
- Group related cases in `unittest.TestCase` classes
- Add regression tests for bug fixes, especially around parsing, Git edge cases, and provider handling

## Commit Message Convention

Use Conventional Commits:

```text
type(scope): short imperative subject
```

Examples:

- `feat(cli): add token counting mode`
- `fix(git): preserve filename encoding in status parsing`
- `docs: clarify Gemini environment setup`

Keep each commit focused on one logical change.

## Pull Request Checklist

Include the following in your PR description:

- Concise summary of behavior changes
- Linked issue/task (if available)
- Test evidence (command and result)
- CLI output snippet when terminal UX changes

Before requesting review, verify:

- Tests pass locally
- Docs are updated when behavior or flags change
- No real API keys/tokens are committed

## Versioning and Releases

Package version sources:

- `src/lazy_commit/__init__.py` (`__version__`)
- `pyproject.toml` (`project.version`)

Release rule:

- Update both files in the same PR and keep versions identical.

Semantic versioning policy:

- Patch (`0.1.1`): bug fixes/refactors without behavior break
- Minor (`0.2.0`): backward-compatible features/flags
- Major (`1.0.0`): breaking CLI/API/config changes

Do not bump version for docs-only or test-only changes.

## Security and Configuration

- Never commit real API keys or tokens.
- Use environment variables for local configuration:
  - `LAZY_COMMIT_API_KEY`
  - `LAZY_COMMIT_BASE_URL`
  - `LAZY_COMMIT_OPENAI_MODEL_NAME`
- Use placeholder values in docs and examples.

## Design Reference

For architecture rationale and runtime flow, see:

- `docs/PROJECT_DESIGN.md`
