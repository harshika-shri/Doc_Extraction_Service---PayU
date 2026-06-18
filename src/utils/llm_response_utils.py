import json
import re
import urllib.error
import urllib.request
from typing import Any

from src.config.settings import settings
from src.core.exceptions.llm_exc import LLMServiceError

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

    message = choices[0].get("message", {})
    content = message.get("content", "")

    if not content:
        raise LLMServiceError(
            "LLM response did not contain content",
            provider="groq",
        )

    return extract_json_text(
        str(content).strip(),
    )


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
) -> str:
    _validate_groq_configuration()

    selected_model = model or settings.GROQ_LLM_MODEL
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
    }

    response_payload = _post_groq_json(
        request_body,
        api_key=settings.GROQ_API_KEY,
    )

    return extract_chat_completion_text(
        response_payload,
    )


def call_groq_classification_llm(
    prompt: str,
) -> str:
    return call_groq_llm(
        prompt,
    )
