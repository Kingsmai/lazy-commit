"""LLM provider abstraction for OpenAI and Gemini APIs."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .config import GEMINI_PROVIDER, OPENAI_PROVIDER, Settings
from .errors import LLMError
from .prompting import PromptPayload

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_USER_AGENT = "lazy-commit/0.1.0"


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


def _extract_error_message(detail: str) -> str:
    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
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


def _format_http_error(code: int, detail: str, url: str) -> str:
    safe_url = _sanitize_url(url)
    lower = detail.lower()
    if code == 403 and "1010" in lower:
        return (
            "HTTP 403 (error code 1010) while calling model API. "
            "This usually means network/WAF blocking or a wrong API base URL. "
            f"Endpoint={safe_url}. For OpenAI, set LAZY_COMMIT_BASE_URL=https://api.openai.com/v1; "
            "for Gemini, set LAZY_COMMIT_BASE_URL=https://generativelanguage.googleapis.com/v1beta."
        )
    return f"HTTP {code} while calling model API ({safe_url}): {_extract_error_message(detail)}"


def _post_json(
    url: str,
    body: dict,
    headers: dict[str, str],
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url=url, method="POST", data=payload, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMError(_format_http_error(exc.code, detail, url)) from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"Failed to call model API: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model API returned invalid JSON payload: {raw[:300]}") from exc


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
