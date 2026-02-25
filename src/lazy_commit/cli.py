"""CLI entrypoint for lazy-commit."""

from __future__ import annotations

import argparse
import sys

from .clipboard import copy_text
from .commit_message import parse_commit_proposal
from .config import load_settings
from .errors import ConfigError, GitError, LLMError, LazyCommitError
from .git_ops import GitClient
from .i18n import (
    detect_language,
    is_affirmative,
    peek_cli_language,
    set_language,
    t,
)
from .llm import LLMClient
from .prompting import build_prompt
from .token_count import DEFAULT_TOKEN_MODEL, count_tokens
from . import ui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lazy-commit",
        description=t("cli.description"),
    )
    parser.add_argument("--api-key", help=t("cli.help.api_key"))
    parser.add_argument("--base-url", help=t("cli.help.base_url"))
    parser.add_argument(
        "--model",
        help=t("cli.help.model"),
    )
    parser.add_argument(
        "--max-context-size",
        type=int,
        help=t("cli.help.max_context_size"),
    )
    parser.add_argument(
        "--max-context-tokens",
        type=int,
        help=t("cli.help.max_context_tokens"),
    )
    parser.add_argument(
        "--count-tokens",
        nargs="?",
        const="-",
        metavar="TEXT",
        help=t("cli.help.count_tokens"),
    )
    parser.add_argument(
        "--token-model",
        help=t("cli.help.token_model", default_token_model=DEFAULT_TOKEN_MODEL),
    )
    parser.add_argument(
        "--token-encoding",
        help=t("cli.help.token_encoding"),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=t("cli.help.apply"),
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help=t("cli.help.push"),
    )
    parser.add_argument(
        "--stage-all",
        action="store_true",
        help=t("cli.help.stage_all"),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help=t("cli.help.yes"),
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help=t("cli.help.remote"),
    )
    parser.add_argument(
        "--branch",
        help=t("cli.help.branch"),
    )
    parser.add_argument(
        "--show-context",
        action="store_true",
        help=t("cli.help.show_context"),
    )
    parser.add_argument(
        "--show-raw-response",
        action="store_true",
        help=t("cli.help.show_raw_response"),
    )
    parser.add_argument(
        "--lang",
        help=t("cli.help.lang"),
    )
    parser.set_defaults(copy=True)
    parser.add_argument(
        "--copy",
        dest="copy",
        action="store_true",
        help=t("cli.help.copy"),
    )
    parser.add_argument(
        "--no-copy",
        dest="copy",
        action="store_false",
        help=t("cli.help.no_copy"),
    )
    return parser


def _confirm(prompt: str) -> bool:
    answer = input(prompt)
    return is_affirmative(answer)


def _resolve_token_input(value: str) -> str:
    if value != "-":
        return value
    if sys.stdin.isatty():
        raise ConfigError(t("cli.error.count_tokens_stdin_required"))
    return sys.stdin.read()


def run(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    set_language(detect_language(peek_cli_language(raw_argv)))

    args = build_parser().parse_args(raw_argv)
    set_language(args.lang)

    if args.count_tokens is not None:
        token_text = _resolve_token_input(args.count_tokens)
        token_model = args.token_model or DEFAULT_TOKEN_MODEL
        result = count_tokens(
            token_text,
            model_name=token_model,
            encoding_name=args.token_encoding,
        )
        print(ui.rule("="))
        print(ui.section(t("cli.section.token_count")))
        print(ui.key_value(t("cli.label.model"), result.model_name))
        print(ui.key_value(t("cli.label.encoding"), result.encoding_name))
        print(ui.key_value(t("cli.label.characters"), str(result.character_count)))
        print(ui.key_value(t("cli.label.tokens"), str(result.token_count)))
        print(ui.rule("="))
        return 0

    if args.push and not args.apply:
        raise ConfigError(t("cli.error.push_requires_apply"))

    print(ui.rule("="))
    print(ui.section(t("cli.section.execution_log")))
    print(ui.info(t("cli.log.loading_settings")))
    settings = load_settings(
        api_key=args.api_key,
        base_url=args.base_url,
        model_name=args.model,
        max_context_size=args.max_context_size,
        max_context_tokens=args.max_context_tokens,
    )

    print(ui.info(t("cli.log.checking_repo")))
    git = GitClient()
    git.ensure_repo()
    print(ui.info(t("cli.log.collecting_snapshot")))
    snapshot = git.snapshot()
    if not snapshot.has_any_changes:
        print(ui.warn(t("cli.log.no_local_changes")))
        print(ui.rule("="))
        return 0

    print(ui.info(t("cli.log.building_context")))
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
                t(
                    "cli.log.estimated_prompt_tokens",
                    total_tokens_after=usage.total_tokens_after,
                    context_tokens_after=usage.context_tokens_after,
                    model_name=usage.model_name,
                    encoding_name=usage.encoding_name,
                )
            )
        )
        if usage.token_limit is not None:
            print(
                ui.info(
                    t(
                        "cli.log.context_token_budget",
                        context_tokens_after=usage.context_tokens_after,
                        token_limit=usage.token_limit,
                        context_tokens_before=usage.context_tokens_before,
                    )
                )
            )
            if usage.compression_applied:
                steps = ", ".join(usage.compression_steps)
                print(
                    ui.warn(
                        t("cli.log.context_compression_applied", steps=steps)
                    )
                )
    if args.show_context:
        print(ui.rule("="))
        print(ui.section(t("cli.section.context_sent_to_model")))
        print(prompt_payload.context)
        print(ui.rule("="))

    print(
        ui.info(
            t(
                "cli.log.requesting_commit_proposal",
                provider=settings.provider,
                model_name=settings.model_name,
            )
        )
    )
    client = LLMClient(settings)
    llm_response = client.complete(prompt_payload)

    if args.show_raw_response:
        print(ui.rule("="))
        print(ui.section(t("cli.section.raw_model_response")))
        print(llm_response.text)
        print(ui.rule("="))

    print(ui.info(t("cli.log.parsing_model_response")))
    proposal = parse_commit_proposal(llm_response.text)
    final_message = proposal.to_commit_message()

    print(ui.rule("="))
    print(ui.section(t("cli.section.generation_summary")))
    print(
        ui.render_generation_summary(
            provider=settings.provider,
            model=settings.model_name,
            branch=snapshot.branch,
            file_count=len(snapshot.changed_files),
        )
    )
    print(ui.section(t("cli.section.changed_files")))
    print(ui.render_files(snapshot.changed_files))
    print("")
    print(ui.section(t("cli.section.generated_commit_message")))
    print(ui.render_message_box(final_message))

    if args.copy:
        copy_result = copy_text(final_message)
        if copy_result.ok:
            print(ui.success(copy_result.detail))
        else:
            print(ui.warn(copy_result.detail))

    if not args.apply:
        print(ui.info(t("cli.log.preview_only")))
        print(ui.rule("="))
        return 0

    if args.stage_all:
        print(ui.info(t("cli.log.staging_all")))
        git.stage_all()

    # Commit requires staged changes.
    if not git.snapshot().has_staged_changes:
        raise GitError(t("cli.error.no_staged_changes"))

    if not args.yes and not _confirm(t("cli.prompt.apply_commit")):
        print(ui.warn(t("cli.log.aborted_by_user")))
        print(ui.rule("="))
        return 1

    print(ui.info(t("cli.log.creating_commit")))
    commit_output = git.commit(final_message)
    print(commit_output)

    if args.push:
        branch = args.branch or git.current_branch()
        print(ui.info(t("cli.log.pushing", remote=args.remote, branch=branch)))
        push_output = git.push(args.remote, branch)
        print(push_output)

    print(ui.success(t("cli.log.done")))
    print(ui.rule("="))
    return 0


def main() -> None:
    try:
        raise SystemExit(run())
    except (ConfigError, GitError, LLMError, LazyCommitError) as exc:
        print(ui.error(t("cli.error.prefix", error=exc)), file=sys.stderr)
        raise SystemExit(2) from exc
    except KeyboardInterrupt:
        print(f"\n{t('cli.log.interrupted')}", file=sys.stderr)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
