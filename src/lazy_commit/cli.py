"""CLI entrypoint for lazy-commit."""

from __future__ import annotations

import argparse
import sys

from .clipboard import copy_text
from .commit_message import parse_commit_proposal
from .config import load_settings
from .errors import ConfigError, GitError, LLMError, LazyCommitError
from .git_ops import GitClient
from .llm import LLMClient
from .prompting import build_prompt
from .token_count import DEFAULT_TOKEN_MODEL, count_tokens
from . import ui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lazy-commit",
        description=(
            "Understand git changes, generate a normalized commit message, "
            "and optionally apply/push in one command."
        ),
    )
    parser.add_argument("--api-key", help="Override LAZY_COMMIT_API_KEY")
    parser.add_argument("--base-url", help="Override LAZY_COMMIT_BASE_URL")
    parser.add_argument(
        "--model",
        help="Override LAZY_COMMIT_OPENAI_MODEL_NAME (also used for Gemini model id).",
    )
    parser.add_argument(
        "--max-context-size",
        type=int,
        help="Override LAZY_COMMIT_MAX_CONTEXT_SIZE in characters.",
    )
    parser.add_argument(
        "--max-context-tokens",
        type=int,
        help="Override LAZY_COMMIT_MAX_CONTEXT_TOKENS for token-aware context compression.",
    )
    parser.add_argument(
        "--count-tokens",
        nargs="?",
        const="-",
        metavar="TEXT",
        help="Count tokens for TEXT and exit. If TEXT is omitted, read from stdin.",
    )
    parser.add_argument(
        "--token-model",
        help=(
            "Tokenizer model for token counting and estimation. "
            f"In --count-tokens mode defaults to {DEFAULT_TOKEN_MODEL}; "
            "in generation mode defaults to --model/LAZY_COMMIT_OPENAI_MODEL_NAME."
        ),
    )
    parser.add_argument(
        "--token-encoding",
        help=(
            "Override tokenizer encoding for token counting and prompt estimation "
            "(for example: o200k_base)."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Run git commit with the generated message.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push after commit. Requires --apply.",
    )
    parser.add_argument(
        "--stage-all",
        action="store_true",
        help="Stage all tracked/untracked changes before commit.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt when --apply is set.",
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Remote used by --push (default: origin).",
    )
    parser.add_argument(
        "--branch",
        help="Branch used by --push (default: current branch).",
    )
    parser.add_argument(
        "--show-context",
        action="store_true",
        help="Print trimmed git context sent to the model.",
    )
    parser.add_argument(
        "--show-raw-response",
        action="store_true",
        help="Print raw model response before parsing.",
    )
    parser.set_defaults(copy=True)
    parser.add_argument(
        "--copy",
        dest="copy",
        action="store_true",
        help="Copy generated commit message to clipboard (default: enabled).",
    )
    parser.add_argument(
        "--no-copy",
        dest="copy",
        action="store_false",
        help="Disable clipboard copy.",
    )
    return parser


def _confirm(prompt: str) -> bool:
    answer = input(prompt).strip().lower()
    return answer in {"y", "yes"}


def _resolve_token_input(value: str) -> str:
    if value != "-":
        return value
    if sys.stdin.isatty():
        raise ConfigError("--count-tokens without TEXT requires piped stdin.")
    return sys.stdin.read()


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.count_tokens is not None:
        token_text = _resolve_token_input(args.count_tokens)
        token_model = args.token_model or DEFAULT_TOKEN_MODEL
        result = count_tokens(
            token_text,
            model_name=token_model,
            encoding_name=args.token_encoding,
        )
        print(ui.rule("="))
        print(ui.section("Token Count"))
        print(ui.key_value("Model", result.model_name))
        print(ui.key_value("Encoding", result.encoding_name))
        print(ui.key_value("Characters", str(result.character_count)))
        print(ui.key_value("Tokens", str(result.token_count)))
        print(ui.rule("="))
        return 0

    if args.push and not args.apply:
        raise ConfigError("--push requires --apply.")

    print(ui.rule("="))
    print(ui.section("Execution Log"))
    print(ui.info("Loading settings..."))
    settings = load_settings(
        api_key=args.api_key,
        base_url=args.base_url,
        model_name=args.model,
        max_context_size=args.max_context_size,
        max_context_tokens=args.max_context_tokens,
    )

    print(ui.info("Checking git repository..."))
    git = GitClient()
    git.ensure_repo()
    print(ui.info("Collecting git snapshot..."))
    snapshot = git.snapshot()
    if not snapshot.has_any_changes:
        print(ui.warn("No local changes found. Nothing to generate."))
        print(ui.rule("="))
        return 0

    print(ui.info("Building model context..."))
    prompt_token_model = args.token_model or settings.model_name
    prompt_payload = build_prompt(
        snapshot,
        max_chars=settings.max_context_size,
        max_tokens=settings.max_context_tokens,
        token_model=prompt_token_model,
        token_encoding=args.token_encoding,
    )
    if prompt_payload.token_usage is not None:
        usage = prompt_payload.token_usage
        print(
            ui.info(
                "Estimated prompt tokens: "
                f"total {usage.total_tokens_after} / context {usage.context_tokens_after} "
                f"(model={usage.model_name}, encoding={usage.encoding_name})."
            )
        )
        if usage.token_limit is not None:
            print(
                ui.info(
                    "Context token budget: "
                    f"{usage.context_tokens_after}/{usage.token_limit} "
                    f"(before compression: {usage.context_tokens_before})."
                )
            )
            if usage.compression_applied:
                steps = ", ".join(usage.compression_steps)
                print(
                    ui.warn(
                        "Context exceeded token budget; compression applied: "
                        f"{steps}."
                    )
                )
    if args.show_context:
        print(ui.rule("="))
        print(ui.section("Context Sent To Model"))
        print(prompt_payload.context)
        print(ui.rule("="))

    print(
        ui.info(
            f"Requesting commit proposal ({settings.provider}/{settings.model_name})..."
        )
    )
    client = LLMClient(settings)
    llm_response = client.complete(prompt_payload)

    if args.show_raw_response:
        print(ui.rule("="))
        print(ui.section("Raw Model Response"))
        print(llm_response.text)
        print(ui.rule("="))

    print(ui.info("Parsing model response..."))
    proposal = parse_commit_proposal(llm_response.text)
    final_message = proposal.to_commit_message()

    print(ui.rule("="))
    print(ui.section("Generation Summary"))
    print(
        ui.render_generation_summary(
            provider=settings.provider,
            model=settings.model_name,
            branch=snapshot.branch,
            file_count=len(snapshot.changed_files),
        )
    )
    print(ui.section("Changed Files"))
    print(ui.render_files(snapshot.changed_files))
    print("")
    print(ui.section("Generated Commit Message"))
    print(ui.render_message_box(final_message))

    if args.copy:
        copy_result = copy_text(final_message)
        if copy_result.ok:
            print(ui.success(copy_result.detail))
        else:
            print(ui.warn(copy_result.detail))

    if not args.apply:
        print(ui.info("Preview only. Re-run with --apply to create commit."))
        print(ui.rule("="))
        return 0

    if args.stage_all:
        print(ui.info("Staging all changes..."))
        git.stage_all()

    # Commit requires staged changes.
    if not git.snapshot().has_staged_changes:
        raise GitError("No staged changes. Use --stage-all or stage files manually.")

    if not args.yes and not _confirm("Apply this commit message? [y/N]: "):
        print(ui.warn("Aborted by user."))
        print(ui.rule("="))
        return 1

    print(ui.info("Creating commit..."))
    commit_output = git.commit(final_message)
    print(commit_output)

    if args.push:
        branch = args.branch or git.current_branch()
        print(ui.info(f"Pushing to {args.remote}/{branch}..."))
        push_output = git.push(args.remote, branch)
        print(push_output)

    print(ui.success("Done."))
    print(ui.rule("="))
    return 0


def main() -> None:
    try:
        raise SystemExit(run())
    except (ConfigError, GitError, LLMError, LazyCommitError) as exc:
        print(ui.error(f"lazy-commit error: {exc}"), file=sys.stderr)
        raise SystemExit(2) from exc
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
