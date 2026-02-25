"""Language selection and message translation helpers."""

from __future__ import annotations

import os
from typing import Mapping, Sequence

DEFAULT_LANGUAGE = "en"
ZH_CN_LANGUAGE = "zh-cn"

_ALIASES = {
    "en": DEFAULT_LANGUAGE,
    "en-us": DEFAULT_LANGUAGE,
    "en-gb": DEFAULT_LANGUAGE,
    "zh": ZH_CN_LANGUAGE,
    "zh-cn": ZH_CN_LANGUAGE,
    "zh-hans": ZH_CN_LANGUAGE,
    "zh-sg": ZH_CN_LANGUAGE,
    "cn": ZH_CN_LANGUAGE,
}

_TRANSLATIONS: dict[str, dict[str, str]] = {
    DEFAULT_LANGUAGE: {
        "cli.description": (
            "Understand git changes, generate a normalized commit message, "
            "and optionally apply/push in one command."
        ),
        "cli.help.api_key": "Override LAZY_COMMIT_API_KEY",
        "cli.help.base_url": "Override LAZY_COMMIT_BASE_URL",
        "cli.help.model": "Override LAZY_COMMIT_OPENAI_MODEL_NAME (also used for Gemini model id).",
        "cli.help.max_context_size": "Override LAZY_COMMIT_MAX_CONTEXT_SIZE in characters.",
        "cli.help.max_context_tokens": "Override LAZY_COMMIT_MAX_CONTEXT_TOKENS for token-aware context compression.",
        "cli.help.count_tokens": "Count tokens for TEXT and exit. If TEXT is omitted, read from stdin.",
        "cli.help.token_model": (
            "Tokenizer model for token counting and estimation. "
            "In --count-tokens mode defaults to {default_token_model}; "
            "in generation mode defaults to --model/LAZY_COMMIT_OPENAI_MODEL_NAME."
        ),
        "cli.help.token_encoding": (
            "Override tokenizer encoding for token counting and prompt estimation "
            "(for example: o200k_base)."
        ),
        "cli.help.apply": "Run git commit with the generated message.",
        "cli.help.push": "Push after commit. Requires --apply.",
        "cli.help.stage_all": "Stage all tracked/untracked changes before commit.",
        "cli.help.yes": "Skip confirmation prompt when --apply is set.",
        "cli.help.remote": "Remote used by --push (default: origin).",
        "cli.help.branch": "Branch used by --push (default: current branch).",
        "cli.help.show_context": "Print trimmed git context sent to the model.",
        "cli.help.show_raw_response": "Print raw model response before parsing.",
        "cli.help.copy": "Copy generated commit message to clipboard (default: enabled).",
        "cli.help.no_copy": "Disable clipboard copy.",
        "cli.help.lang": "UI language (for example: en, zh-CN). Defaults to LAZY_COMMIT_LANG or English.",
        "cli.error.count_tokens_stdin_required": "--count-tokens without TEXT requires piped stdin.",
        "cli.error.push_requires_apply": "--push requires --apply.",
        "cli.error.no_staged_changes": "No staged changes. Use --stage-all or stage files manually.",
        "cli.error.prefix": "lazy-commit error: {error}",
        "cli.section.token_count": "Token Count",
        "cli.section.execution_log": "Execution Log",
        "cli.section.context_sent_to_model": "Context Sent To Model",
        "cli.section.raw_model_response": "Raw Model Response",
        "cli.section.generation_summary": "Generation Summary",
        "cli.section.changed_files": "Changed Files",
        "cli.section.generated_commit_message": "Generated Commit Message",
        "cli.label.model": "Model",
        "cli.label.encoding": "Encoding",
        "cli.label.characters": "Characters",
        "cli.label.tokens": "Tokens",
        "cli.log.loading_settings": "Loading settings...",
        "cli.log.checking_repo": "Checking git repository...",
        "cli.log.collecting_snapshot": "Collecting git snapshot...",
        "cli.log.no_local_changes": "No local changes found. Nothing to generate.",
        "cli.log.building_context": "Building model context...",
        "cli.log.estimated_prompt_tokens": (
            "Estimated prompt tokens: total {total_tokens_after} / context {context_tokens_after} "
            "(model={model_name}, encoding={encoding_name})."
        ),
        "cli.log.context_token_budget": (
            "Context token budget: {context_tokens_after}/{token_limit} "
            "(before compression: {context_tokens_before})."
        ),
        "cli.log.context_compression_applied": "Context exceeded token budget; compression applied: {steps}.",
        "cli.log.requesting_commit_proposal": "Requesting commit proposal ({provider}/{model_name})...",
        "cli.log.parsing_model_response": "Parsing model response...",
        "cli.log.preview_only": "Preview only. Re-run with --apply to create commit.",
        "cli.log.staging_all": "Staging all changes...",
        "cli.prompt.apply_commit": "Apply this commit message? [y/N]: ",
        "cli.log.aborted_by_user": "Aborted by user.",
        "cli.log.creating_commit": "Creating commit...",
        "cli.log.pushing": "Pushing to {remote}/{branch}...",
        "cli.log.done": "Done.",
        "cli.log.interrupted": "Interrupted.",
        "clipboard.error.command_not_found": "Clipboard command not found. Install one of: {commands}.",
        "clipboard.success.copied_via": "Copied to clipboard via {command}.",
        "clipboard.error.copy_failed_all": "Clipboard copy failed for all commands: {failures}",
        "clipboard.error.copy_failed": "Clipboard copy failed.",
        "ui.level.info": "INFO",
        "ui.level.ok": "OK",
        "ui.level.warn": "WARN",
        "ui.level.error": "ERROR",
        "ui.field.provider": "Provider",
        "ui.field.model": "Model",
        "ui.field.branch": "Branch",
        "ui.field.files": "Files",
        "ui.table.field": "Field",
        "ui.table.value": "Value",
        "ui.table.path": "Path",
        "ui.none": "(none)",
        "ui.commit_message_title": "Commit Message",
    },
    ZH_CN_LANGUAGE: {
        "cli.description": "理解 Git 变更，生成规范化提交信息，并可在一个命令中提交/推送。",
        "cli.help.api_key": "覆盖 LAZY_COMMIT_API_KEY",
        "cli.help.base_url": "覆盖 LAZY_COMMIT_BASE_URL",
        "cli.help.model": "覆盖 LAZY_COMMIT_OPENAI_MODEL_NAME（Gemini 模型 id 也使用该参数）。",
        "cli.help.max_context_size": "覆盖 LAZY_COMMIT_MAX_CONTEXT_SIZE（字符数）。",
        "cli.help.max_context_tokens": "覆盖 LAZY_COMMIT_MAX_CONTEXT_TOKENS（基于 token 的上下文压缩预算）。",
        "cli.help.count_tokens": "统计 TEXT 的 token 并退出；省略 TEXT 时从 stdin 读取。",
        "cli.help.token_model": (
            "用于 token 统计与估算的 tokenizer 模型。"
            "在 --count-tokens 模式下默认 {default_token_model}；"
            "在生成模式下默认 --model/LAZY_COMMIT_OPENAI_MODEL_NAME。"
        ),
        "cli.help.token_encoding": "覆盖 token 统计与提示估算使用的编码（例如：o200k_base）。",
        "cli.help.apply": "使用生成的提交信息执行 git commit。",
        "cli.help.push": "提交后推送。需要 --apply。",
        "cli.help.stage_all": "提交前暂存所有已跟踪/未跟踪变更。",
        "cli.help.yes": "启用 --apply 时跳过确认提示。",
        "cli.help.remote": "--push 使用的远端（默认：origin）。",
        "cli.help.branch": "--push 使用的分支（默认：当前分支）。",
        "cli.help.show_context": "打印发送给模型的裁剪后 Git 上下文。",
        "cli.help.show_raw_response": "解析前打印模型原始响应。",
        "cli.help.copy": "将生成的提交信息复制到剪贴板（默认开启）。",
        "cli.help.no_copy": "关闭剪贴板复制。",
        "cli.help.lang": "界面语言（例如：en、zh-CN）。默认取 LAZY_COMMIT_LANG，否则英文。",
        "cli.error.count_tokens_stdin_required": "--count-tokens 未提供 TEXT 时需要通过管道输入 stdin。",
        "cli.error.push_requires_apply": "--push 需要 --apply。",
        "cli.error.no_staged_changes": "没有已暂存的变更。请使用 --stage-all 或手动暂存文件。",
        "cli.error.prefix": "lazy-commit 错误：{error}",
        "cli.section.token_count": "Token 统计",
        "cli.section.execution_log": "执行日志",
        "cli.section.context_sent_to_model": "发送给模型的上下文",
        "cli.section.raw_model_response": "模型原始响应",
        "cli.section.generation_summary": "生成摘要",
        "cli.section.changed_files": "变更文件",
        "cli.section.generated_commit_message": "生成的提交信息",
        "cli.label.model": "模型",
        "cli.label.encoding": "编码",
        "cli.label.characters": "字符数",
        "cli.label.tokens": "Token 数",
        "cli.log.loading_settings": "正在加载配置...",
        "cli.log.checking_repo": "正在检查 Git 仓库...",
        "cli.log.collecting_snapshot": "正在收集 Git 快照...",
        "cli.log.no_local_changes": "未发现本地变更，无需生成提交信息。",
        "cli.log.building_context": "正在构建模型上下文...",
        "cli.log.estimated_prompt_tokens": (
            "估算提示 token：总计 {total_tokens_after} / 上下文 {context_tokens_after} "
            "(模型={model_name}, 编码={encoding_name})。"
        ),
        "cli.log.context_token_budget": (
            "上下文 token 预算：{context_tokens_after}/{token_limit} "
            "(压缩前：{context_tokens_before})。"
        ),
        "cli.log.context_compression_applied": "上下文超出 token 预算，已执行压缩：{steps}。",
        "cli.log.requesting_commit_proposal": "正在请求提交建议（{provider}/{model_name}）...",
        "cli.log.parsing_model_response": "正在解析模型响应...",
        "cli.log.preview_only": "仅预览。使用 --apply 可创建提交。",
        "cli.log.staging_all": "正在暂存所有变更...",
        "cli.prompt.apply_commit": "是否应用该提交信息？[y/N]: ",
        "cli.log.aborted_by_user": "用户已取消。",
        "cli.log.creating_commit": "正在创建提交...",
        "cli.log.pushing": "正在推送到 {remote}/{branch}...",
        "cli.log.done": "完成。",
        "cli.log.interrupted": "已中断。",
        "clipboard.error.command_not_found": "未找到剪贴板命令。请安装以下任一工具：{commands}。",
        "clipboard.success.copied_via": "已通过 {command} 复制到剪贴板。",
        "clipboard.error.copy_failed_all": "所有剪贴板命令都复制失败：{failures}",
        "clipboard.error.copy_failed": "复制到剪贴板失败。",
        "ui.level.info": "信息",
        "ui.level.ok": "成功",
        "ui.level.warn": "警告",
        "ui.level.error": "错误",
        "ui.field.provider": "提供方",
        "ui.field.model": "模型",
        "ui.field.branch": "分支",
        "ui.field.files": "文件数",
        "ui.table.field": "字段",
        "ui.table.value": "值",
        "ui.table.path": "路径",
        "ui.none": "(无)",
        "ui.commit_message_title": "提交信息",
    },
}

_YES_ANSWERS: dict[str, set[str]] = {
    DEFAULT_LANGUAGE: {"y", "yes"},
    ZH_CN_LANGUAGE: {"y", "yes", "是"},
}

_current_language = DEFAULT_LANGUAGE


def normalize_language(value: str | None) -> str:
    if not value:
        return DEFAULT_LANGUAGE

    normalized = value.strip().lower().replace("_", "-")
    if not normalized:
        return DEFAULT_LANGUAGE
    if normalized in _ALIASES:
        return _ALIASES[normalized]
    if normalized.startswith("zh"):
        return ZH_CN_LANGUAGE
    if normalized.startswith("en"):
        return DEFAULT_LANGUAGE
    return DEFAULT_LANGUAGE


def detect_language(preferred: str | None = None, env: Mapping[str, str] | None = None) -> str:
    if preferred and preferred.strip():
        return normalize_language(preferred)

    resolved_env = os.environ if env is None else env
    return normalize_language(resolved_env.get("LAZY_COMMIT_LANG"))


def set_language(language: str | None) -> str:
    global _current_language
    _current_language = detect_language(language)
    return _current_language


def get_language() -> str:
    return _current_language


def peek_cli_language(argv: Sequence[str]) -> str | None:
    for index, arg in enumerate(argv):
        if arg == "--lang":
            if index + 1 >= len(argv):
                return None
            next_arg = argv[index + 1]
            if next_arg.startswith("-"):
                return None
            return next_arg
        if arg.startswith("--lang="):
            return arg.split("=", maxsplit=1)[1]
    return None


def t(key: str, **kwargs: object) -> str:
    text = _TRANSLATIONS.get(_current_language, {}).get(key)
    if text is None:
        text = _TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)

    if not kwargs:
        return text

    try:
        return text.format(**kwargs)
    except (IndexError, KeyError, ValueError):
        return text


def is_affirmative(answer: str) -> bool:
    normalized = answer.strip().lower()
    if not normalized:
        return False

    accepted = _YES_ANSWERS.get(_current_language, set()) | _YES_ANSWERS[DEFAULT_LANGUAGE]
    return normalized in accepted
