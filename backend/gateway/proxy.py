from __future__ import annotations

import httpx
from fastapi import APIRouter, Request, Response

from gateway.config import settings

router = APIRouter()

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


@router.api_route("/api/projects/{project_id}/questions", methods=["GET", "OPTIONS"])
async def proxy_project_questions(project_id: str, request: Request) -> Response:
    return await _forward(request, settings.question_service_url)


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


@router.api_route(
    "/api/projects/{project_id}/questions/{question_id}/answer",
    methods=["POST", "OPTIONS"],
)
async def proxy_project_question_answer(
    project_id: str, question_id: str, request: Request
) -> Response:
    return await _forward(request, settings.question_service_url)


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

    upstream = await _client.request(
        request.method,
        url,
        headers=headers,
        content=body,
        timeout=timeout,
    )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )
