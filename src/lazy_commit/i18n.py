"""Language selection and message translation helpers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from importlib import resources
from string import Formatter
from typing import Any, Mapping, Sequence

DEFAULT_LANGUAGE = "en"
ZH_CN_LANGUAGE = "zh-cn"
ZH_TW_LANGUAGE = "zh-tw"

_FALLBACK_YES_ANSWERS = {"y", "yes"}


@dataclass(frozen=True)
class LanguageInfo:
    code: str
    name: str
    aliases: tuple[str, ...]


def _normalize_token(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower().replace("_", "-")


def _normalize_aliases(raw_aliases: object, language: str) -> tuple[str, ...]:
    aliases: list[str] = [language]
    if isinstance(raw_aliases, list):
        for item in raw_aliases:
            if not isinstance(item, str):
                continue
            normalized = _normalize_token(item)
            if normalized and normalized not in aliases:
                aliases.append(normalized)
    return tuple(aliases)


def _normalize_yes_answers(raw_answers: object, language: str) -> set[str]:
    answers: set[str] = set()
    if isinstance(raw_answers, list):
        for item in raw_answers:
            if not isinstance(item, str):
                continue
            normalized = item.strip().lower()
            if normalized:
                answers.add(normalized)
    if language == DEFAULT_LANGUAGE:
        answers |= _FALLBACK_YES_ANSWERS
    return answers


def _normalize_messages(raw_messages: object, language: str, issues: list[str]) -> dict[str, str]:
    if not isinstance(raw_messages, dict):
        issues.append(f"{language}: 'messages' must be a JSON object.")
        return {}

    messages: dict[str, str] = {}
    for key, value in raw_messages.items():
        if not isinstance(key, str):
            issues.append(f"{language}: non-string message key ignored.")
            continue
        if not isinstance(value, str):
            issues.append(f"{language}: '{key}' must map to a string.")
            continue
        messages[key] = value
    return messages


def _normalize_name(raw_name: object, language: str) -> str:
    if isinstance(raw_name, str):
        text = raw_name.strip()
        if text:
            return text
    return language


def _extract_placeholders(template: str) -> set[str]:
    placeholders: set[str] = set()
    for _, field_name, _, _ in Formatter().parse(template):
        if not field_name:
            continue
        normalized = field_name.split(".", maxsplit=1)[0].split("[", maxsplit=1)[0]
        if normalized:
            placeholders.add(normalized)
    return placeholders


def _register_aliases(
    alias_map: dict[str, str], aliases: tuple[str, ...], language: str, issues: list[str]
) -> None:
    for alias in aliases:
        existing = alias_map.get(alias)
        if existing is None:
            alias_map[alias] = language
            continue
        if existing != language:
            issues.append(
                f"{language}: alias '{alias}' conflicts with '{existing}', keeping '{existing}'."
            )


def _read_locale_payloads() -> tuple[dict[str, dict[str, Any]], list[str]]:
    locale_dir = resources.files("lazy_commit").joinpath("locales")
    try:
        entries = sorted(locale_dir.iterdir(), key=lambda item: item.name)
    except FileNotFoundError as exc:
        raise RuntimeError("Missing locale directory: lazy_commit/locales") from exc

    payloads: dict[str, dict[str, Any]] = {}
    issues: list[str] = []

    for entry in entries:
        if not entry.name.endswith(".json"):
            continue
        language = _normalize_token(entry.name.rsplit(".", maxsplit=1)[0])
        if not language:
            continue

        try:
            with entry.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            issues.append(f"{language}: failed to load locale file: {exc}.")
            continue

        if not isinstance(payload, dict):
            issues.append(f"{language}: locale file must contain a JSON object.")
            continue

        payloads[language] = payload

    return payloads, issues


def _build_catalog() -> tuple[
    dict[str, dict[str, str]],
    dict[str, str],
    dict[str, set[str]],
    dict[str, str],
    dict[str, tuple[str, ...]],
    tuple[str, ...],
]:
    raw_payloads, issues = _read_locale_payloads()

    default_payload = raw_payloads.get(DEFAULT_LANGUAGE)
    if default_payload is None:
        raise RuntimeError("Missing default locale file: lazy_commit/locales/en.json")

    default_messages = _normalize_messages(
        default_payload.get("messages"), DEFAULT_LANGUAGE, issues
    )
    if not default_messages:
        raise RuntimeError("Default locale does not define any messages.")

    translations: dict[str, dict[str, str]] = {
        DEFAULT_LANGUAGE: dict(default_messages),
    }
    alias_map: dict[str, str] = {}
    yes_answers: dict[str, set[str]] = {
        DEFAULT_LANGUAGE: _normalize_yes_answers(
            default_payload.get("yes_answers"), DEFAULT_LANGUAGE
        ),
    }
    language_names: dict[str, str] = {
        DEFAULT_LANGUAGE: _normalize_name(default_payload.get("name"), DEFAULT_LANGUAGE),
    }

    default_aliases = _normalize_aliases(default_payload.get("aliases"), DEFAULT_LANGUAGE)
    _register_aliases(alias_map, default_aliases, DEFAULT_LANGUAGE, issues)

    for language in sorted(raw_payloads):
        if language == DEFAULT_LANGUAGE:
            continue

        payload = raw_payloads[language]
        localized_messages = _normalize_messages(payload.get("messages"), language, issues)
        merged_messages = dict(default_messages)
        provided_keys = set(localized_messages)

        for key, text in localized_messages.items():
            default_text = default_messages.get(key)
            if default_text is None:
                issues.append(
                    f"{language}: key '{key}' is not present in {DEFAULT_LANGUAGE}."
                )
                merged_messages[key] = text
                continue

            if _extract_placeholders(text) != _extract_placeholders(default_text):
                issues.append(
                    f"{language}: placeholder mismatch for '{key}', falling back to {DEFAULT_LANGUAGE}."
                )
                continue

            merged_messages[key] = text

        for key in sorted(set(default_messages) - provided_keys):
            issues.append(
                f"{language}: missing key '{key}', falling back to {DEFAULT_LANGUAGE}."
            )

        translations[language] = merged_messages
        yes_answers[language] = _normalize_yes_answers(payload.get("yes_answers"), language)
        language_names[language] = _normalize_name(payload.get("name"), language)
        aliases = _normalize_aliases(payload.get("aliases"), language)
        _register_aliases(alias_map, aliases, language, issues)

    if DEFAULT_LANGUAGE not in alias_map:
        alias_map[DEFAULT_LANGUAGE] = DEFAULT_LANGUAGE

    aliases_by_language: dict[str, tuple[str, ...]] = {}
    for language in translations:
        aliases_by_language[language] = tuple(
            sorted(
                alias
                for alias, target in alias_map.items()
                if target == language and alias != language
            )
        )

    return (
        translations,
        alias_map,
        yes_answers,
        language_names,
        aliases_by_language,
        tuple(issues),
    )


(
    _TRANSLATIONS,
    _ALIASES,
    _YES_ANSWERS,
    _LANGUAGE_NAMES,
    _ALIASES_BY_LANGUAGE,
    _TRANSLATION_ISSUES,
) = _build_catalog()

_current_language = DEFAULT_LANGUAGE


def available_languages() -> list[LanguageInfo]:
    ordered_languages = [DEFAULT_LANGUAGE] + sorted(
        code for code in _TRANSLATIONS if code != DEFAULT_LANGUAGE
    )
    return [
        LanguageInfo(
            code=code,
            name=_LANGUAGE_NAMES.get(code, code),
            aliases=_ALIASES_BY_LANGUAGE.get(code, ()),
        )
        for code in ordered_languages
    ]


def translation_issues() -> tuple[str, ...]:
    return _TRANSLATION_ISSUES


def normalize_language(value: str | None) -> str:
    if not value:
        return DEFAULT_LANGUAGE

    normalized = _normalize_token(value)
    if not normalized:
        return DEFAULT_LANGUAGE

    aliased = _ALIASES.get(normalized)
    if aliased:
        return aliased

    if normalized in _TRANSLATIONS:
        return normalized

    base = normalized.split("-", maxsplit=1)[0]
    aliased_base = _ALIASES.get(base)
    if aliased_base:
        return aliased_base
    if base in _TRANSLATIONS:
        return base

    if normalized.startswith("zh"):
        if (
            ZH_TW_LANGUAGE in _TRANSLATIONS
            and any(marker in normalized for marker in ("-tw", "-hk", "-mo", "-hant"))
        ):
            return ZH_TW_LANGUAGE
        if ZH_CN_LANGUAGE in _TRANSLATIONS:
            return ZH_CN_LANGUAGE
        if ZH_TW_LANGUAGE in _TRANSLATIONS:
            return ZH_TW_LANGUAGE
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

    accepted = _YES_ANSWERS.get(_current_language, set()) | _YES_ANSWERS.get(
        DEFAULT_LANGUAGE, _FALLBACK_YES_ANSWERS
    )
    return normalized in accepted
