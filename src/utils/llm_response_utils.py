import json
import re
import time
import urllib.error
import urllib.request
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from src.config.llm_config import (
    GROQ_MODEL_EXTRACTION,
    GROQ_MODEL_PARSE_INVOICE,
)
from src.config.settings import settings
from src.core.exceptions.llm_exc import LLMServiceError

TModel = TypeVar(
    "TModel",
    bound=BaseModel,
)

_THINKING_BLOCK_PATTERN = re.compile(
    "<"
    "think"
    r">[\s\S]*?</"
    "think"
    ">",
    flags=re.IGNORECASE | re.DOTALL,
)

_GROQ_HTTP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (compatible; DocExtractionService/1.0; "
        "+https://api.groq.com)"
    ),
}


def _strip_model_reasoning(
    response_text: str,
) -> str:
    return _THINKING_BLOCK_PATTERN.sub(
        "",
        response_text,
    ).strip()


def extract_json_text(
    response_text: str,
) -> str:
    stripped_text = _strip_model_reasoning(
        response_text,
    )

    if stripped_text.startswith(
        "{",
    ) or stripped_text.startswith(
        "[",
    ):
        return stripped_text

    fenced_match = re.search(
        r"```(?:json)?\s*([\s\S]*?)\s*```",
        stripped_text,
    )

    if fenced_match:
        return fenced_match.group(
            1,
        ).strip()

    return stripped_text


def trim_raw_extraction_for_llm(
    raw_extraction: str,
    *,
    max_chars: int = 14000,
    max_document_text_chars: int = 10000,
) -> str:
    try:
        payload = json.loads(
            raw_extraction,
        )
    except json.JSONDecodeError:
        return raw_extraction[
            :max_chars
        ]

    if not isinstance(
        payload,
        dict,
    ):
        return raw_extraction[
            :max_chars
        ]

    document_text = payload.get(
        "full_document_text",
    )

    if (
        isinstance(
            document_text,
            str,
        )
        and len(document_text)
        > max_document_text_chars
    ):
        payload[
            "full_document_text"
        ] = (
            document_text[
                :max_document_text_chars
            ]
            + "\n...[truncated]"
        )

    trimmed = json.dumps(
        payload,
        ensure_ascii=False,
    )

    if len(trimmed) > max_chars:
        return trimmed[:max_chars]

    return trimmed


def extract_classification_snippet(
    raw_extraction: str,
    *,
    max_chars: int,
) -> str:
    try:
        payload = json.loads(
            raw_extraction,
        )
    except json.JSONDecodeError:
        return raw_extraction[
            :max_chars
        ]

    if not isinstance(
        payload,
        dict,
    ):
        return raw_extraction[
            :max_chars
        ]

    document_text = payload.get(
        "full_document_text",
        "",
    )

    if isinstance(
        document_text,
        str,
    ) and document_text.strip():
        return document_text[
            :max_chars
        ]

    return raw_extraction[
        :max_chars
    ]


def _is_rate_limit_error(
    error: LLMServiceError,
) -> bool:
    if error.status_code in {
        413,
        429,
    }:
        return True

    detail = error.detail.lower()

    return (
        "rate_limit_exceeded" in detail
        or "request too large" in detail
        or "tokens per minute" in detail
    )


def _parse_retry_after_seconds(
    error: LLMServiceError,
) -> float | None:
    """Extract the suggested retry-after delay from a Groq 429 error message."""
    import re as _re

    minute_match = _re.search(
        r"try again in (\d+)m([\d.]+)s",
        error.detail,
        flags=_re.IGNORECASE,
    )

    if minute_match:
        return (
            int(minute_match.group(1)) * 60
            + float(minute_match.group(2))
            + 1
        )

    second_match = _re.search(
        r"try again in ([\d.]+)s",
        error.detail,
        flags=_re.IGNORECASE,
    )

    if second_match:
        return float(second_match.group(1)) + 1

    return None


_SHORT_RATE_LIMIT_THRESHOLD_SECONDS = 65
_INLINE_MAX_RETRIES = 5

def _build_llm_error_detail(
    status_code: int,
    error_body: str,
) -> str:
    if "error code: 1010" in error_body.lower():
        return (
            "Groq API request was blocked by the network "
            "(Cloudflare 1010). Restart the service after "
            "confirming GROQ_API_KEY is set in .env."
        )

    if status_code in (401, 403):
        if error_body.strip():
            return (
                "Groq API key is invalid or unauthorized: "
                f"{error_body.strip()}"
            )

        return (
            "Groq API key is invalid or unauthorized."
        )

    if error_body.strip():
        return (
            f"Groq API request failed with HTTP "
            f"{status_code}: {error_body.strip()}"
        )

    return (
        f"Groq API request failed with HTTP "
        f"{status_code}."
    )


def _is_qwen_model(
    model: str,
) -> bool:
    return "qwen" in model.lower()


def _is_json_validate_failed(
    error: LLMServiceError,
) -> bool:
    return (
        error.status_code == 400
        and "json_validate_failed" in error.detail
    )


def _configure_groq_json_request(
    request_body: dict[str, Any],
    *,
    model: str,
) -> None:
    if not _is_qwen_model(
        model,
    ):
        return

    request_body["reasoning_effort"] = "none"
    request_body["reasoning_format"] = "parsed"


def _post_groq_json(
    request_body: dict[str, Any],
    *,
    api_key: str,
    timeout: int = 120,
) -> dict[str, Any]:
    headers = {
        **_GROQ_HTTP_HEADERS,
        "Authorization": (
            f"Bearer {api_key}"
        ),
    }
    request = urllib.request.Request(
        url=(
            f"{settings.GROQ_API_BASE_URL.rstrip('/')}"
            "/chat/completions"
        ),
        data=json.dumps(
            request_body,
        ).encode(
            "utf-8",
        ),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            return json.loads(
                response.read().decode(
                    "utf-8",
                ),
            )
    except urllib.error.HTTPError as error:
        error_body = error.read().decode(
            "utf-8",
        )

        raise LLMServiceError(
            _build_llm_error_detail(
                status_code=error.code,
                error_body=error_body,
            ),
            provider="groq",
            status_code=error.code,
        ) from error


def extract_chat_completion_text(
    response_payload: dict[str, Any],
) -> str:
    choices = response_payload.get("choices", [])

    if not choices:
        raise LLMServiceError(
            "LLM response did not contain choices",
            provider="groq",
        )

    choice = choices[0]
    message = choice.get("message", {})
    content = message.get("content", "")
    finish_reason = choice.get(
        "finish_reason",
    )

    if not content:
        raise LLMServiceError(
            "LLM response did not contain content",
            provider="groq",
        )

    if finish_reason == "length":
        raise LLMServiceError(
            "LLM response was truncated before "
            "completion. Increase "
            "GROQ_LLM_MAX_TOKENS or reduce "
            "input size.",
            provider="groq",
        )

    return extract_json_text(
        str(content).strip(),
    )


def parse_llm_model(
    response_text: str,
    model_cls: type[TModel],
) -> TModel:
    json_text = extract_json_text(
        response_text,
    )

    try:
        return model_cls.model_validate_json(
            json_text,
        )
    except ValidationError as error:
        preview = json_text[:200]
        raise LLMServiceError(
            "LLM returned invalid JSON for "
            f"{model_cls.__name__}: {error}. "
            f"Preview: {preview}",
            provider="groq",
        ) from error


def _validate_groq_configuration() -> None:
    if not settings.GROQ_API_KEY:
        raise LLMServiceError(
            "GROQ_API_KEY is not configured",
            provider="groq",
        )


def call_groq_llm(
    prompt: str,
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    max_retries: int = 2,
) -> str:
    _validate_groq_configuration()

    selected_model = (
        model or GROQ_MODEL_PARSE_INVOICE
    )
    selected_max_tokens = (
        max_tokens
        if max_tokens is not None
        else settings.GROQ_LLM_MAX_TOKENS
    )
    request_body: dict[str, Any] = {
        "model": selected_model,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\n"
                    "Return valid JSON only."
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": selected_max_tokens,
        "response_format": {
            "type": "json_object",
        },
    }
    _configure_groq_json_request(
        request_body,
        model=selected_model,
    )

    last_error: LLMServiceError | None = None

    for attempt in range(
        _INLINE_MAX_RETRIES + 1,
    ):
        try:
            response_payload = _post_groq_json(
                request_body,
                api_key=settings.GROQ_API_KEY,
            )

            return extract_chat_completion_text(
                response_payload,
            )
        except LLMServiceError as error:
            last_error = error

            if (
                attempt == 0
                and _is_json_validate_failed(
                    error,
                )
                and "response_format" in request_body
            ):
                request_body.pop(
                    "response_format",
                    None,
                )
                request_body.pop(
                    "reasoning_effort",
                    None,
                )
                request_body.pop(
                    "reasoning_format",
                    None,
                )
                continue

            if (
                attempt < _INLINE_MAX_RETRIES
                and _is_rate_limit_error(
                    error,
                )
            ):
                wait = _parse_retry_after_seconds(
                    error,
                )

                if (
                    wait is not None
                    and wait
                    < _SHORT_RATE_LIMIT_THRESHOLD_SECONDS
                ):
                    time.sleep(wait)
                    continue

                raise

            raise

    if last_error is not None:
        raise last_error

    raise LLMServiceError(
        "Groq API request failed.",
        provider="groq",
    )


def call_groq_vision_llm(
    prompt: str,
    image_data_urls: list[str],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    max_retries: int = 2,
) -> str:
    _validate_groq_configuration()

    if not image_data_urls:
        raise LLMServiceError(
            "At least one document image is required for vision extraction.",
            provider="groq",
            status_code=400,
        )

    selected_model = (
        model or GROQ_MODEL_EXTRACTION
    )
    selected_max_tokens = (
        max_tokens
        if max_tokens is not None
        else settings.GROQ_LLM_MAX_TOKENS
    )

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                f"{prompt}\n\n"
                "Return valid JSON only."
            ),
        },
    ]

    for image_data_url in image_data_urls:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": image_data_url,
                },
            },
        )

    request_body: dict[str, Any] = {
        "model": selected_model,
        "messages": [
            {
                "role": "user",
                "content": content,
            },
        ],
        "temperature": 0,
        "max_tokens": selected_max_tokens,
        "response_format": {
            "type": "json_object",
        },
    }
    _configure_groq_json_request(
        request_body,
        model=selected_model,
    )

    last_error: LLMServiceError | None = None

    for attempt in range(
        _INLINE_MAX_RETRIES + 1,
    ):
        try:
            response_payload = _post_groq_json(
                request_body,
                api_key=settings.GROQ_API_KEY,
                timeout=180,
            )

            return extract_chat_completion_text(
                response_payload,
            )
        except LLMServiceError as error:
            last_error = error

            if (
                attempt == 0
                and _is_json_validate_failed(
                    error,
                )
                and "response_format" in request_body
            ):
                request_body.pop(
                    "response_format",
                    None,
                )
                request_body.pop(
                    "reasoning_effort",
                    None,
                )
                request_body.pop(
                    "reasoning_format",
                    None,
                )
                continue

            if (
                attempt < _INLINE_MAX_RETRIES
                and _is_rate_limit_error(
                    error,
                )
            ):
                wait = _parse_retry_after_seconds(
                    error,
                )

                if (
                    wait is not None
                    and wait
                    < _SHORT_RATE_LIMIT_THRESHOLD_SECONDS
                ):
                    time.sleep(wait)
                    continue

                raise

            raise

    if last_error is not None:
        raise last_error

    raise LLMServiceError(
        "Groq API request failed.",
        provider="groq",
    )


def call_groq_classification_llm(
    prompt: str,
    *,
    model: str,
) -> str:
    return call_groq_llm(
        prompt,
        model=model,
    )
