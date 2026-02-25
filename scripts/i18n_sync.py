#!/usr/bin/env python3
"""Generate pending translation templates by diffing against en.json."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Any

DEFAULT_LOCALES_DIR = Path("src/lazy_commit/locales")
DEFAULT_BASE_LOCALE = "en"


@dataclass(frozen=True)
class PendingAnalysis:
    missing_keys: tuple[str, ...]
    empty_values: tuple[str, ...]
    placeholder_mismatch: tuple[str, ...]
    obsolete_keys: tuple[str, ...]

    @property
    def total_pending(self) -> int:
        return len(self.pending_keys)

    @property
    def pending_keys(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                set(self.missing_keys)
                | set(self.empty_values)
                | set(self.placeholder_mismatch)
            )
        )


def _normalize_locale_token(value: str) -> str:
    token = value.strip().lower().replace("_", "-")
    if token.endswith(".json"):
        token = token[:-5]
    return token


def _extract_placeholders(template: str) -> set[str]:
    placeholders: set[str] = set()
    for _, field_name, _, _ in Formatter().parse(template):
        if not field_name:
            continue
        normalized = field_name.split(".", maxsplit=1)[0].split("[", maxsplit=1)[0]
        if normalized:
            placeholders.add(normalized)
    return placeholders


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: top-level JSON must be an object.")
    return payload


def _normalize_messages(raw_messages: object, path: Path) -> dict[str, str]:
    if not isinstance(raw_messages, dict):
        raise ValueError(f"{path}: 'messages' must be a JSON object.")

    messages: dict[str, str] = {}
    for key, value in raw_messages.items():
        if not isinstance(key, str):
            raise ValueError(f"{path}: message keys must be strings.")
        if not isinstance(value, str):
            raise ValueError(f"{path}: value for '{key}' must be a string.")
        messages[key] = value
    return messages


def _normalize_string_list(raw_values: object, fallback: list[str]) -> list[str]:
    if not isinstance(raw_values, list):
        return fallback

    values: list[str] = []
    for item in raw_values:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if text and text not in values:
            values.append(text)
    return values if values else fallback


def _analyze_messages(base_messages: dict[str, str], target_messages: dict[str, str]) -> PendingAnalysis:
    missing_keys: list[str] = []
    empty_values: list[str] = []
    placeholder_mismatch: list[str] = []

    for key, base_text in base_messages.items():
        localized_text = target_messages.get(key)
        if localized_text is None:
            missing_keys.append(key)
            continue
        if not localized_text.strip():
            empty_values.append(key)
            continue
        if _extract_placeholders(localized_text) != _extract_placeholders(base_text):
            placeholder_mismatch.append(key)

    obsolete_keys = sorted(key for key in target_messages if key not in base_messages)

    return PendingAnalysis(
        missing_keys=tuple(sorted(missing_keys)),
        empty_values=tuple(sorted(empty_values)),
        placeholder_mismatch=tuple(sorted(placeholder_mismatch)),
        obsolete_keys=tuple(obsolete_keys),
    )


def _build_template_payload(
    locale_code: str,
    base_locale: str,
    base_messages: dict[str, str],
    target_catalog: dict[str, Any],
    analysis: PendingAnalysis,
) -> dict[str, Any]:
    pending_messages = {key: base_messages[key] for key in analysis.pending_keys}
    locale_name = target_catalog.get("name")
    name = locale_name.strip() if isinstance(locale_name, str) and locale_name.strip() else locale_code

    aliases = _normalize_string_list(target_catalog.get("aliases"), [locale_code])
    yes_answers = _normalize_string_list(target_catalog.get("yes_answers"), ["y", "yes"])

    return {
        "name": name,
        "aliases": aliases,
        "yes_answers": yes_answers,
        "messages": pending_messages,
        "_meta": {
            "locale": locale_code,
            "base_locale": base_locale,
            "missing_keys": len(analysis.missing_keys),
            "empty_values": len(analysis.empty_values),
            "placeholder_mismatch": len(analysis.placeholder_mismatch),
            "obsolete_keys": len(analysis.obsolete_keys),
            "total_pending": analysis.total_pending,
            "note": (
                "Translate values in 'messages' and keep placeholders "
                "(for example {count}, {model_name}) unchanged."
            ),
        },
    }


def _resolve_locale_codes(
    locales_dir: Path, base_locale: str, raw_locales: list[str] | None
) -> list[str]:
    if raw_locales:
        resolved: list[str] = []
        for item in raw_locales:
            normalized = _normalize_locale_token(item)
            if normalized and normalized != base_locale:
                resolved.append(normalized)
        return list(dict.fromkeys(resolved))

    discovered = [
        _normalize_locale_token(path.stem)
        for path in sorted(locales_dir.glob("*.json"))
        if _normalize_locale_token(path.stem) and _normalize_locale_token(path.stem) != base_locale
    ]
    return list(dict.fromkeys(discovered))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare locale catalogs with en.json and generate pending translation templates."
        )
    )
    parser.add_argument(
        "--locales-dir",
        default=str(DEFAULT_LOCALES_DIR),
        help="Locale directory containing *.json files (default: src/lazy_commit/locales).",
    )
    parser.add_argument(
        "--base-locale",
        default=DEFAULT_BASE_LOCALE,
        help="Base locale code used as the source of truth (default: en).",
    )
    parser.add_argument(
        "--locale",
        action="append",
        help=(
            "Target locale code to sync (for example: zh-CN). "
            "Can be provided multiple times. Defaults to all non-base locales."
        ),
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for generated templates (default: <locales-dir>/pending).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary without writing files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    locales_dir = Path(args.locales_dir)
    base_locale = _normalize_locale_token(args.base_locale) or DEFAULT_BASE_LOCALE
    output_dir = Path(args.output_dir) if args.output_dir else locales_dir / "pending"

    base_locale_file = locales_dir / f"{base_locale}.json"
    if not base_locale_file.exists():
        print(f"error: base locale file not found: {base_locale_file}", file=sys.stderr)
        return 2

    try:
        base_catalog = _read_json(base_locale_file)
        base_messages = _normalize_messages(base_catalog.get("messages"), base_locale_file)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: failed to load base locale: {exc}", file=sys.stderr)
        return 2

    locale_codes = _resolve_locale_codes(locales_dir, base_locale, args.locale)
    if not locale_codes:
        print("No target locales found.")
        return 0

    generated_count = 0
    up_to_date_count = 0

    for locale_code in locale_codes:
        target_locale_file = locales_dir / f"{locale_code}.json"

        if target_locale_file.exists():
            try:
                target_catalog = _read_json(target_locale_file)
                target_messages = _normalize_messages(
                    target_catalog.get("messages"), target_locale_file
                )
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                print(f"error: failed to load target locale '{locale_code}': {exc}", file=sys.stderr)
                return 2
        else:
            target_catalog = {
                "name": locale_code,
                "aliases": [locale_code],
                "yes_answers": ["y", "yes"],
                "messages": {},
            }
            target_messages = {}

        analysis = _analyze_messages(base_messages, target_messages)
        template_path = output_dir / f"{locale_code}.pending.json"

        if analysis.total_pending == 0:
            up_to_date_count += 1
            if template_path.exists() and not args.dry_run:
                template_path.unlink()
                print(f"{locale_code}: up-to-date (removed stale template).")
            else:
                print(f"{locale_code}: up-to-date.")
            continue

        payload = _build_template_payload(
            locale_code=locale_code,
            base_locale=base_locale,
            base_messages=base_messages,
            target_catalog=target_catalog,
            analysis=analysis,
        )

        if not args.dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)
            with template_path.open("w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")

        generated_count += 1
        print(
            f"{locale_code}: pending={analysis.total_pending} "
            f"(missing={len(analysis.missing_keys)}, "
            f"empty={len(analysis.empty_values)}, "
            f"placeholder_mismatch={len(analysis.placeholder_mismatch)}, "
            f"obsolete={len(analysis.obsolete_keys)}) -> {template_path}"
        )

    print(
        f"Done. generated={generated_count}, up_to_date={up_to_date_count}, "
        f"total={len(locale_codes)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
