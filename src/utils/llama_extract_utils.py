import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from src.config.settings import settings
from src.constants.llama_extract_schemas import (
    INVOICE_RAW_EXTRACTION_SCHEMA,
    PURCHASE_ORDER_EXTRACTION_SCHEMA,
)
from src.core.exceptions.llm_exc import LLMServiceError
from src.utils.file_utils import (
    guess_mime_type,
)

_RESOLVED_PROJECT_ID: str | None = None


def _build_llama_error_detail(
    status_code: int,
    error_body: str,
) -> str:
    if status_code in (401, 403):
        return (
            "Llama Cloud API key is invalid or unauthorized."
        )

    if "project_id" in error_body.lower():
        return (
            "Llama Cloud project ID is missing or invalid. "
            "Set LLAMA_CLOUD_PROJECT_ID in .env."
        )

    if error_body.strip():
        return (
            f"Llama Cloud API request failed with HTTP "
            f"{status_code}: {error_body.strip()}"
        )

    return (
        f"Llama Cloud API request failed with HTTP "
        f"{status_code}."
    )


def _request_json(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    headers = {
        "Authorization": (
            f"Bearer {settings.LLAMA_CLOUD_API_KEY}"
        ),
        "Accept": "application/json",
    }

    if content_type is not None:
        headers["Content-Type"] = content_type

    request = urllib.request.Request(
        url=url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=120,
        ) as response:
            payload = json.loads(
                response.read().decode(
                    "utf-8",
                ),
            )

            if isinstance(payload, dict):
                return payload

            return {"data": payload}
    except urllib.error.HTTPError as error:
        error_body = error.read().decode(
            "utf-8",
        )

        raise LLMServiceError(
            _build_llama_error_detail(
                error.code,
                error_body,
            ),
            provider="llama",
            status_code=error.code,
        ) from error


def _encode_multipart_form(
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body_parts: list[bytes] = []

    for name, value in fields.items():
        body_parts.extend(
            [
                f"--{boundary}".encode(),
                (
                    f'Content-Disposition: form-data; name="{name}"'
                ).encode(),
                b"",
                value.encode(),
            ],
        )

    for name, (
        filename,
        file_bytes,
        mime_type,
    ) in files.items():
        body_parts.extend(
            [
                f"--{boundary}".encode(),
                (
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{filename}"'
                ).encode(),
                f"Content-Type: {mime_type}".encode(),
                b"",
                file_bytes,
            ],
        )

    body_parts.extend(
        [
            f"--{boundary}--".encode(),
            b"",
        ],
    )

    return b"\r\n".join(body_parts), boundary


def _validate_llama_configuration() -> None:
    if not settings.LLAMA_CLOUD_API_KEY:
        raise LLMServiceError(
            "LLAMA_CLOUD_API_KEY is not configured",
            provider="llama",
        )


def _resolve_project_id() -> str:
    global _RESOLVED_PROJECT_ID

    if settings.LLAMA_CLOUD_PROJECT_ID:
        return settings.LLAMA_CLOUD_PROJECT_ID

    if _RESOLVED_PROJECT_ID:
        return _RESOLVED_PROJECT_ID

    projects_response = _request_json(
        f"{settings.LLAMA_CLOUD_API_BASE_URL.rstrip('/')}"
        "/api/v1/projects",
    )

    if isinstance(projects_response, list):
        projects = projects_response
    else:
        projects = projects_response.get(
            "data",
            projects_response,
        )

    if not isinstance(projects, list):
        raise LLMServiceError(
            "Unable to resolve Llama Cloud project ID.",
            provider="llama",
        )

    default_project = next(
        (
            project
            for project in projects
            if project.get("is_default")
        ),
        None,
    )
    selected_project = default_project or (
        projects[0] if projects else None
    )

    project_id = (
        selected_project.get("id")
        if isinstance(selected_project, dict)
        else None
    )

    if not project_id:
        raise LLMServiceError(
            "No Llama Cloud project found for this API key.",
            provider="llama",
        )

    _RESOLVED_PROJECT_ID = str(project_id)
    return _RESOLVED_PROJECT_ID


def _upload_file(
    file_path: Path,
) -> str:
    file_bytes = file_path.read_bytes()
    mime_type = guess_mime_type(
        file_path,
    )
    form_body, boundary = _encode_multipart_form(
        fields={
            "purpose": "extract",
        },
        files={
            "file": (
                file_path.name,
                file_bytes,
                mime_type,
            ),
        },
    )

    response = _request_json(
        url=(
            f"{settings.LLAMA_CLOUD_API_BASE_URL.rstrip('/')}"
            "/api/v1/beta/files"
        ),
        method="POST",
        body=form_body,
        content_type=(
            f"multipart/form-data; boundary={boundary}"
        ),
    )

    file_id = response.get("id")
    if not file_id:
        raise LLMServiceError(
            "Llama Cloud file upload did not return a file ID.",
            provider="llama",
        )

    return str(file_id)


def _create_extract_job(
    file_id: str,
    data_schema: dict[str, object],
    *,
    system_prompt: str | None = None,
) -> str:
    project_id = _resolve_project_id()
    configuration: dict[str, object] = {
        "tier": settings.LLAMA_EXTRACT_TIER,
        "extraction_target": "per_doc",
        "confidence_scores": False,
        "data_schema": data_schema,
    }

    if system_prompt:
        configuration["system_prompt"] = system_prompt

    request_body = {
        "file_input": file_id,
        "configuration": configuration,
    }
    query = urllib.parse.urlencode(
        {
            "project_id": project_id,
        },
    )

    response = _request_json(
        url=(
            f"{settings.LLAMA_CLOUD_API_BASE_URL.rstrip('/')}"
            f"/api/v2/extract?{query}"
        ),
        method="POST",
        body=json.dumps(
            request_body,
        ).encode("utf-8"),
        content_type="application/json",
    )

    job_id = response.get("id")
    if not job_id:
        raise LLMServiceError(
            "LlamaExtract job creation did not return a job ID.",
            provider="llama",
        )

    return str(job_id)


def _poll_extract_job(
    job_id: str,
) -> dict[str, Any]:
    project_id = _resolve_project_id()
    query = urllib.parse.urlencode(
        {
            "project_id": project_id,
        },
    )
    status_url = (
        f"{settings.LLAMA_CLOUD_API_BASE_URL.rstrip('/')}"
        f"/api/v2/extract/{job_id}?{query}"
    )

    for _ in range(
        settings.LLAMA_EXTRACT_POLL_MAX_ATTEMPTS,
    ):
        response = _request_json(
            status_url,
        )
        status = str(
            response.get(
                "status",
                "",
            ),
        ).upper()

        if status == "COMPLETED":
            extract_result = response.get(
                "extract_result",
            )
            if isinstance(extract_result, dict):
                return extract_result

            if extract_result is not None:
                return {
                    "data": extract_result,
                }

            return response

        if status in {"FAILED", "CANCELLED"}:
            error_detail = response.get("error")
            if isinstance(error_detail, dict):
                error_detail = error_detail.get(
                    "detail",
                    "LlamaExtract job failed.",
                )

            raise LLMServiceError(
                str(
                    error_detail
                    or "LlamaExtract job failed.",
                ),
                provider="llama",
            )

        time.sleep(
            settings.LLAMA_EXTRACT_POLL_INTERVAL_SECONDS,
        )

    raise LLMServiceError(
        "LlamaExtract job timed out while polling for results.",
        provider="llama",
    )


def _normalize_extract_result(
    extract_result: dict[str, Any],
) -> dict[str, Any]:
    nested_data = extract_result.get(
        "data",
    )

    if isinstance(
        nested_data,
        dict,
    ) and nested_data:
        return nested_data

    return extract_result


def run_llama_extract_job(
    file_path: Path,
    data_schema: dict[str, object],
    *,
    system_prompt: str | None = None,
) -> str:
    _validate_llama_configuration()

    file_id = _upload_file(
        file_path,
    )
    job_id = _create_extract_job(
        file_id=file_id,
        data_schema=data_schema,
        system_prompt=system_prompt,
    )
    extract_result = _poll_extract_job(
        job_id,
    )

    normalized_result = _normalize_extract_result(
        extract_result,
    )

    return json.dumps(
        normalized_result,
        indent=2,
        default=str,
    )


def extract_invoice_document(
    file_path: Path,
) -> str:
    raw_extraction = run_llama_extract_job(
        file_path=file_path,
        data_schema=INVOICE_RAW_EXTRACTION_SCHEMA,
        system_prompt=(
            "Extract all visible invoice content from the document. "
            "Preserve tables, amounts, party details, tax values, "
            "and line items in the raw output."
        ),
    )

    print("\n" + "=" * 80)
    print("RAW LLAMA INVOICE EXTRACTION")
    print("=" * 80)
    print(
        f"File: {file_path}",
    )
    print(raw_extraction)

    return raw_extraction


def extract_purchase_order_document(
    file_path: Path,
) -> str:
    raw_extraction = run_llama_extract_job(
        file_path=file_path,
        data_schema=PURCHASE_ORDER_EXTRACTION_SCHEMA,
        system_prompt=(
            "Extract purchase order fields using the provided schema. "
            "Map buyer and supplier details correctly and capture "
            "every visible line item."
        ),
    )

    print("\n" + "=" * 80)
    print("RAW LLAMA PURCHASE ORDER EXTRACTION")
    print("=" * 80)
    print(
        f"File: {file_path}",
    )
    print(raw_extraction)

    return raw_extraction
