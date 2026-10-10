"""Interactive onboarding for first-time and returning CLI users."""

from __future__ import annotations

import getpass
import os
import sys
import warnings
from urllib.parse import urlsplit

from .config import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_MODEL,
    detect_provider,
    read_user_config,
    save_user_config,
)
from .errors import ConfigError
from .i18n import get_language, is_affirmative, normalize_language, set_language, t

_OPENAI_URL = "https://api.openai.com/v1"
_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"


def _ask(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    return input(f"{label}{suffix}: ").strip() or default


def _choice(label: str, default: str, allowed: set[str]) -> str:
    while True:
        answer = _ask(label, default)
        if answer in allowed:
            return answer
        print(t("setup.invalid_choice"))


def _valid_url(value: str) -> bool:
    try:
        url = urlsplit(value)
        url.port  # Validate a port when present.
        return bool(
            url.scheme in {"https", "http"} and url.hostname
            and not url.username and not url.password and not url.query and not url.fragment
        )
    except ValueError:
        return False


def run_setup(*, preferred_language: str | None = None) -> int:
    """Collect settings and save only after confirmation; never call an API."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ConfigError(t("setup.requires_terminal"))
    try:
        saved = read_user_config()
    except ConfigError:
        print(t("setup.repair"))
        saved = {}

    try:
        print("\nLazy Commit — 配置向导 / Setup")
        print("1. 简体中文   2. English   3. 繁體中文")
        languages = {"1": "zh-cn", "2": "en", "3": "zh-tw"}
        preferred = normalize_language(
            preferred_language or os.getenv("LAZY_COMMIT_LANG")
            or str(saved.get("language") or "zh-cn")
        )
        default_language = next((key for key, value in languages.items() if value == preferred), "1")
        language = _choice("语言 / Language", default_language, set(languages))
        set_language(languages[language])
        print(t("setup.intro"))

        old_url = str(saved.get("base_url", ""))
        old_model = str(saved.get("model_name", ""))
        default_provider = "1"
        if old_url and old_url.rstrip("/") != _OPENAI_URL:
            default_provider = "2" if detect_provider(old_model, old_url) == "gemini" else "3"
        print(t("setup.providers"))
        provider = _choice(t("setup.provider"), default_provider, {"1", "2", "3"})
        if provider == "1":
            base_url, default_model = _OPENAI_URL, DEFAULT_OPENAI_MODEL
        elif provider == "2":
            base_url, default_model = _GEMINI_URL, DEFAULT_GEMINI_MODEL
        else:
            base_url = ""
            while not _valid_url(base_url):
                base_url = _ask(t("setup.base_url"), old_url if default_provider == "3" else "")
                if not _valid_url(base_url):
                    print(t("setup.invalid_url"))
            base_url = base_url.rstrip("/")
            default_model = ""

        same_endpoint = old_url.rstrip("/") == base_url
        model = _ask(t("setup.model"), old_model if same_endpoint else default_model)
        while not model:
            print(t("setup.required"))
            model = _ask(t("setup.model"))

        existing_key = str(saved.get("api_key", "")) if same_endpoint else ""
        print(t("setup.key_help"))
        key = ""
        while not key:
            prompt = t("setup.key_keep") if existing_key else t("setup.key")
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                try:
                    key = getpass.getpass(prompt).strip() or existing_key
                except getpass.GetPassWarning as exc:
                    raise ConfigError(t("setup.requires_terminal")) from exc
            if not key:
                print(t("setup.required"))

        values = dict(saved)
        values.update(api_key=key, base_url=base_url, model_name=model, language=get_language())
        print(t("setup.summary", base_url=base_url, model=model))
        print(t("setup.storage"))
        if any(os.getenv(name) for name in (
            "LAZY_COMMIT_API_KEY", "LAZY_COMMIT_OPENAI_API_KEY", "LAZY_COMMIT_BASE_URL",
            "LAZY_COMMIT_OPENAI_BASE_URL", "LAZY_COMMIT_OPENAI_MODEL_NAME", "LAZY_COMMIT_LANG",
            "LAZY_COMMIT_MAX_CONTEXT_SIZE", "LAZY_COMMIT_MAX_CONTEXT_TOKENS",
        )):
            print(t("setup.env_override"))
        answer = input(t("setup.confirm")).strip()
        if answer and not is_affirmative(answer):
            print(t("setup.cancelled"))
            return 1
        path = save_user_config(values)
        print(t("setup.saved", path=path))
        print(t("setup.next"))
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\n" + t("setup.cancelled"))
        return 1
