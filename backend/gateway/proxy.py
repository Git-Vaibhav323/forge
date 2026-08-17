from __future__ import annotations

import json
import logging

import httpx
from fastapi import APIRouter, Request, Response

from gateway.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

_client = httpx.AsyncClient(
    timeout=15.0,
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=40),
)


@router.api_route("/api/projects", methods=["GET", "POST", "OPTIONS"])
async def proxy_projects_root(request: Request) -> Response:
    return await _forward(request, settings.project_service_url)


@router.api_route("/api/projects/{project_id}", methods=["GET", "DELETE", "OPTIONS"])
async def proxy_project_detail(project_id: str, request: Request) -> Response:
    return await _forward(request, settings.project_service_url)


@router.api_route("/api/projects/{project_id}/files", methods=["POST", "OPTIONS"])
async def proxy_project_files(project_id: str, request: Request) -> Response:
    return await _forward(request, settings.file_service_url, timeout=120.0)


@router.api_route("/api/projects/{project_id}/sources", methods=["POST", "OPTIONS"])
async def proxy_project_sources(project_id: str, request: Request) -> Response:
    # Fetching a remote catalog page can be slow; allow the same budget as uploads.
    return await _forward(request, settings.file_service_url, timeout=120.0)


@router.api_route("/api/projects/{project_id}/questions", methods=["GET", "OPTIONS"])
async def proxy_project_questions(project_id: str, request: Request) -> Response:
    # ensure_open_question may call the optional LLM planner.
    return await _forward(request, settings.question_service_url, timeout=60.0)


@router.api_route("/api/projects/{project_id}/attributes", methods=["GET", "OPTIONS"])
async def proxy_project_attributes(project_id: str, request: Request) -> Response:
    return await _forward(request, settings.evidence_service_url)


@router.api_route(
    "/api/projects/{project_id}/attributes/extract",
    methods=["POST", "OPTIONS"],
)
async def proxy_project_attributes_extract(project_id: str, request: Request) -> Response:
    # Reading + parsing every PDF can take a while on a remote bucket.
    return await _forward(request, settings.evidence_service_url, timeout=120.0)


@router.api_route("/api/projects/{project_id}/reviews", methods=["GET", "OPTIONS"])
async def proxy_project_reviews(project_id: str, request: Request) -> Response:
    # Derives the queue from the current record before returning it.
    return await _forward(request, settings.review_service_url, timeout=60.0)


@router.api_route("/api/reviews/{review_id}/decision", methods=["POST", "OPTIONS"])
async def proxy_review_decision(review_id: str, request: Request) -> Response:
    # A propagated decision can touch sibling jobs; allow a wider budget.
    return await _forward(request, settings.review_service_url, timeout=60.0)


@router.api_route(
    "/api/projects/{project_id}/outputs", methods=["GET", "POST", "OPTIONS"]
)
async def proxy_project_outputs(project_id: str, request: Request) -> Response:
    # Generating re-derives the whole record before the QA gate runs.
    return await _forward(request, settings.generation_service_url, timeout=120.0)


@router.api_route("/api/outputs/{output_id}/download", methods=["GET", "OPTIONS"])
async def proxy_output_download(output_id: str, request: Request) -> Response:
    return await _forward(request, settings.generation_service_url, timeout=60.0)


@router.api_route("/api/outputs/{output_id}/preview", methods=["GET", "OPTIONS"])
async def proxy_output_preview(output_id: str, request: Request) -> Response:
    return await _forward(request, settings.generation_service_url, timeout=60.0)


@router.api_route(
    "/api/projects/{project_id}/questions/{question_id}/answer",
    methods=["POST", "OPTIONS"],
)
async def proxy_project_question_answer(
    project_id: str, question_id: str, request: Request
) -> Response:
    # Answer + record sync + next-question LLM can exceed the default proxy budget.
    return await _forward(request, settings.question_service_url, timeout=60.0)


async def _forward(request: Request, upstream_base: str, timeout: float = 15.0) -> Response:
    if request.method == "OPTIONS":
        return Response(status_code=204)

    url = f"{upstream_base}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length"}
    }
    body = await request.body()

    try:
        upstream = await _client.request(
            request.method,
            url,
            headers=headers,
            content=body,
            timeout=timeout,
        )
    except httpx.TimeoutException:
        return _error_response(
            504,
            "Upstream service timed out. Try again — the answer may already be saved.",
        )
    except httpx.RequestError as exc:
        logger.exception("Upstream request failed for %s %s", request.method, url)
        return _error_response(502, "Upstream service unavailable.")

    # Content-Disposition must survive the hop or a download arrives unnamed
    # and renders inline instead of saving (M8).
    passthrough = {}
    disposition = upstream.headers.get("content-disposition")
    if disposition:
        passthrough["content-disposition"] = disposition

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
        headers=passthrough or None,
    )


def _error_response(status_code: int, detail: str) -> Response:
    """JSON error bodies so CORS middleware can attach headers on proxy failures."""
    return Response(
        content=json.dumps({"detail": detail}),
        status_code=status_code,
        media_type="application/json",
    )
