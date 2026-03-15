"""LLM provider abstraction for OpenAI and Gemini APIs."""

from __future__ import annotations

import html
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from . import __version__
from .config import GEMINI_PROVIDER, OPENAI_PROVIDER, Settings
from .errors import LLMError
from .i18n import t
from .prompting import PromptPayload

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_TIMEOUT_ATTEMPTS = 2
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_USER_AGENT = f"lazy-commit/{__version__}"


@dataclass(frozen=True)
class LLMResponse:
    """Raw response text from language model."""

    text: str
    provider: str


def _sanitize_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse(parsed._replace(query="", fragment=""))


def _normalize_openai_base_url(base_url: str | None) -> str:
    if not base_url:
        return DEFAULT_OPENAI_BASE_URL

    normalized = base_url.strip().rstrip("/")
    parsed = urllib.parse.urlparse(normalized)
    host = parsed.netloc.lower()
    path = parsed.path or ""

    # Common user mistake: api.openai.com without /v1.
    if host == "api.openai.com" and path in {"", "/"}:
        return normalized + "/v1"

    return normalized


def _compact_text(raw: str, limit: int = 500) -> str:
    compact = " ".join(raw.split())
    return compact[:limit]


def _looks_like_html(detail: str) -> bool:
    stripped = detail.lstrip().casefold()
    if stripped.startswith("<!doctype html") or stripped.startswith("<html"):
        return True
    return "<html" in stripped[:200]


def _extract_html_summary(detail: str) -> str:
    title_match = re.search(
        r"<title[^>]*>(.*?)</title>",
        detail,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if title_match:
        return _compact_text(html.unescape(title_match.group(1)))

    without_blocks = re.sub(
        r"(?is)<(script|style)[^>]*>.*?</\1>",
        " ",
        detail,
    )
    without_tags = re.sub(r"(?s)<[^>]+>", " ", without_blocks)
    return _compact_text(html.unescape(without_tags))


def _extract_error_message(detail: str) -> str:
    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
        if _looks_like_html(detail):
            return _extract_html_summary(detail)
        return _compact_text(detail)

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = str(error.get("message", "")).strip()
            code = str(error.get("code", "")).strip()
            error_type = str(error.get("type", "")).strip()
            pieces = [part for part in [message, f"type={error_type}" if error_type else "", f"code={code}" if code else ""] if part]
            if pieces:
                return "; ".join(pieces)
        return _compact_text(json.dumps(payload, ensure_ascii=True))

    return _compact_text(str(payload))


def _get_header(headers: object | None, name: str) -> str | None:
    if headers is None or not hasattr(headers, "get"):
        return None
    value = headers.get(name)
    if value is None and hasattr(headers, "items"):
        target = name.casefold()
        for key, candidate in headers.items():
            if str(key).casefold() == target:
                value = candidate
                break
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_request_id_detail(headers: object | None) -> str | None:
    for header_name in (
        "x-request-id",
        "request-id",
        "cf-ray",
        "x-correlation-id",
    ):
        value = _get_header(headers, header_name)
        if value:
            return t("llm.error.detail.request_id", header=header_name, value=value)
    return None


def _provider_base_url_hint(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.casefold()
    path = parsed.path.casefold()
    if host == "api.openai.com" or path.endswith("/chat/completions"):
        return t("llm.error.hint.openai_base_url")
    if (
        "generativelanguage.googleapis.com" in host
        or ":generatecontent" in path
        or "/models/" in path
    ):
        return t("llm.error.hint.gemini_base_url")
    return None


def _unique_text(items: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return tuple(unique)


def _build_http_error(
    code: int,
    detail: str,
    url: str,
    *,
    headers: object | None = None,
) -> LLMError:
    safe_url = _sanitize_url(url)
    response_summary = _extract_error_message(detail)
    content_type = _get_header(headers, "Content-Type")
    request_id_detail = _extract_request_id_detail(headers)
    details = [t("llm.error.detail.endpoint", endpoint=safe_url)]
    if content_type:
        details.append(
            t("llm.error.detail.response_content_type", content_type=content_type)
        )
    if response_summary:
        details.append(
            t("llm.error.detail.response_message", response=response_summary)
        )
    if request_id_detail:
        details.append(request_id_detail)

    lower = detail.casefold()
    hints: list[str] = []
    if code == 403 and "1010" in lower:
        message = t("llm.error.http_waf_blocked")
        hints.extend(
            [
                t("llm.error.hint.check_network"),
                t("llm.error.hint.verify_custom_base_url"),
            ]
        )
    elif code in {502, 503, 504}:
        is_html = _looks_like_html(detail)
        message = t(
            "llm.error.http_gateway_html" if is_html else "llm.error.http_gateway",
            code=code,
        )
        if is_html:
            details.append(t("llm.error.detail.gateway_hidden_cause"))
        hints.extend(
            [
                t("llm.error.hint.retry_transient"),
                t("llm.error.hint.verify_custom_base_url"),
            ]
        )
    elif code in {401, 403}:
        message = t("llm.error.http_auth", code=code)
        hints.append(t("llm.error.hint.check_api_key"))
    elif code == 404:
        message = t("llm.error.http_not_found")
        hints.append(t("llm.error.hint.check_model_or_base_url"))
    else:
        message = t("llm.error.http_generic", code=code)
        if code >= 500:
            hints.append(t("llm.error.hint.retry_transient"))

    provider_hint = _provider_base_url_hint(url)
    if provider_hint:
        hints.append(provider_hint)

    return LLMError(
        message,
        details=_unique_text(details),
        hints=_unique_text(hints),
    )


def _format_http_error(code: int, detail: str, url: str) -> str:
    return str(_build_http_error(code, detail, url))


def _build_timeout_error(url: str, timeout: int, attempts: int) -> LLMError:
    safe_url = _sanitize_url(url)
    message = t("llm.error.timeout", timeout=timeout, attempts=attempts)
    details = [t("llm.error.detail.endpoint", endpoint=safe_url)]
    hints = [t("llm.error.hint.check_network")]
    provider_hint = _provider_base_url_hint(url)
    if provider_hint:
        hints.append(provider_hint)
    return LLMError(
        message,
        details=_unique_text(details),
        hints=_unique_text(hints),
    )


def _format_timeout_error(url: str, timeout: int, attempts: int) -> str:
    return str(_build_timeout_error(url, timeout, attempts))


def _build_transport_error(reason: object, url: str) -> LLMError:
    safe_url = _sanitize_url(url)
    details = [t("llm.error.detail.endpoint", endpoint=safe_url)]
    hints = [t("llm.error.hint.check_network")]
    provider_hint = _provider_base_url_hint(url)
    if provider_hint:
        hints.append(provider_hint)
    return LLMError(
        t("llm.error.transport", reason=reason),
        details=_unique_text(details),
        hints=_unique_text(hints),
    )


def _build_invalid_json_error(
    raw: str,
    url: str,
    *,
    headers: object | None = None,
) -> LLMError:
    safe_url = _sanitize_url(url)
    details = [t("llm.error.detail.endpoint", endpoint=safe_url)]
    content_type = _get_header(headers, "Content-Type")
    if content_type:
        details.append(
            t("llm.error.detail.response_content_type", content_type=content_type)
        )
    preview = _extract_error_message(raw[:1000])
    if preview:
        details.append(t("llm.error.detail.response_message", response=preview))
    hints: list[str] = []
    if _looks_like_html(raw):
        hints.append(t("llm.error.hint.verify_custom_base_url"))
        provider_hint = _provider_base_url_hint(url)
        if provider_hint:
            hints.append(provider_hint)
    return LLMError(
        t("llm.error.invalid_json"),
        details=_unique_text(details),
        hints=_unique_text(hints),
    )


def _is_timeout_reason(reason: object) -> bool:
    return isinstance(reason, (TimeoutError, socket.timeout))


def _post_json(
    url: str,
    body: dict,
    headers: dict[str, str],
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    attempts: int = DEFAULT_TIMEOUT_ATTEMPTS,
) -> dict:
    if attempts <= 0:
        raise ValueError("attempts must be a positive integer.")

    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        method="POST",
        data=payload,
        headers=headers,
    )
    last_timeout_error: BaseException | None = None
    response_headers: object | None = None
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                response_headers = getattr(response, "headers", None)
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise _build_http_error(
                exc.code,
                detail,
                url,
                headers=exc.headers,
            ) from exc
        except urllib.error.URLError as exc:
            if _is_timeout_reason(exc.reason):
                last_timeout_error = exc
                continue
            raise _build_transport_error(exc.reason, url) from exc
        except (TimeoutError, socket.timeout) as exc:
            last_timeout_error = exc
            continue
    else:
        raise _build_timeout_error(url, timeout, attempts) from last_timeout_error

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _build_invalid_json_error(
            raw,
            url,
            headers=response_headers,
        ) from exc


class LLMClient:
    """Provider-aware client using the user configuration."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete(self, payload: PromptPayload) -> LLMResponse:
        if self.settings.provider == GEMINI_PROVIDER:
            text = self._complete_gemini(payload)
            return LLMResponse(text=text, provider=GEMINI_PROVIDER)
        if self.settings.provider == OPENAI_PROVIDER:
            text = self._complete_openai(payload)
            return LLMResponse(text=text, provider=OPENAI_PROVIDER)
        raise LLMError(f"Unsupported provider: {self.settings.provider}")

    def _complete_openai(self, payload: PromptPayload) -> str:
        base = _normalize_openai_base_url(self.settings.base_url)
        url = base.rstrip("/") + "/chat/completions"
        body = {
            "model": self.settings.model_name,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": payload.system},
                {"role": "user", "content": payload.user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        data = _post_json(url, body, headers)
        choices = data.get("choices")
        if not choices:
            raise LLMError(f"OpenAI response missing choices: {data}")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise LLMError(f"OpenAI response missing content: {data}")
        return str(content).strip()

    def _complete_gemini(self, payload: PromptPayload) -> str:
        base = self.settings.base_url or DEFAULT_GEMINI_BASE_URL
        if base.rstrip("/").endswith(":generateContent"):
            endpoint = base
        else:
            endpoint = f"{base.rstrip('/')}/models/{self.settings.model_name}:generateContent"

        query = urllib.parse.urlencode({"key": self.settings.api_key})
        url = f"{endpoint}?{query}"
        body = {
            "systemInstruction": {
                "parts": [{"text": payload.system}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": payload.user}],
                }
            ],
            "generationConfig": {"temperature": 0.2},
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        data = _post_json(url, body, headers)
        candidates = data.get("candidates")
        if not candidates:
            raise LLMError(f"Gemini response missing candidates: {data}")
        parts = candidates[0].get("content", {}).get("parts", [])
        text_chunks = [part.get("text", "") for part in parts if part.get("text")]
        content = "\n".join(text_chunks).strip()
        if not content:
            raise LLMError(f"Gemini response missing text content: {data}")
        return content
