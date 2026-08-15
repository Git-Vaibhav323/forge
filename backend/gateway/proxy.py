from __future__ import annotations

import httpx
from fastapi import APIRouter, Request, Response

from gateway.config import settings

router = APIRouter()


@router.api_route("/api/projects", methods=["GET", "POST"])
async def proxy_projects_root(request: Request) -> Response:
    return await _forward(request, settings.project_service_url)


@router.api_route("/api/projects/{project_id}", methods=["GET"])
async def proxy_project_detail(project_id: str, request: Request) -> Response:
    return await _forward(request, settings.project_service_url)


@router.api_route("/api/projects/{project_id}/files", methods=["POST"])
async def proxy_project_files(project_id: str, request: Request) -> Response:
    return await _forward(request, settings.file_service_url, timeout=120.0)


async def _forward(request: Request, upstream_base: str, timeout: float = 30.0) -> Response:
    url = f"{upstream_base}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length"}
    }
    body = await request.body()

    async with httpx.AsyncClient(timeout=timeout) as client:
        upstream = await client.request(
            request.method,
            url,
            headers=headers,
            content=body,
        )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )
