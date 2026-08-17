"""Fetch or accept a web page as citeable source material.

Providers (WEB_FETCH_PROVIDER):
  direct  — httpx GET of the URL (default; works for static HTML catalogs)
  apify   — placeholder for Apify actors (requires APIFY_API_TOKEN + APIFY_ACTOR_ID)
  custom  — POST to WEB_FETCH_API_URL with {url}; expects {html} or {content}

Never invent facts. Whatever comes back is stored as a document and must still
survive the same label→field extraction as a PDF.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from services.file_service.config import settings
from shared.html_text import html_to_text  # noqa: F401 — re-export


class WebFetchError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def validate_public_http_url(url: str, *, resolve_host: bool = True) -> str:
    raw = (url or "").strip()
    if not raw:
        raise WebFetchError("URL is required")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise WebFetchError("Only http(s) URLs are accepted")
    if not parsed.hostname:
        raise WebFetchError("URL is missing a host")
    if resolve_host:
        _reject_private_host(parsed.hostname)
    return raw


def _reject_private_host(hostname: str) -> None:
    host = hostname.lower().strip(".")
    if host in {"localhost", "metadata.google.internal"} or host.endswith(".local"):
        raise WebFetchError("That host is not allowed")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise WebFetchError(f"Could not resolve host: {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise WebFetchError("That host is not allowed")


def _fetch_direct(url: str) -> tuple[str, str]:
    try:
        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            response = client.get(
                url,
                headers={"User-Agent": "ForgeDataEvidenceBot/0.1 (+local)"},
            )
    except httpx.HTTPError as exc:
        raise WebFetchError(f"Could not fetch URL: {exc}", status_code=502) from exc
    if response.status_code >= 400:
        raise WebFetchError(
            f"URL returned HTTP {response.status_code}",
            status_code=502,
        )
    final = str(response.url)
    validate_public_http_url(final)
    content_type = response.headers.get("content-type", "")
    text = response.text
    if "html" not in content_type.lower() and "<html" not in text[:500].lower():
        if "text/" not in content_type.lower() and not text.strip():
            raise WebFetchError("URL did not return HTML or text content", status_code=502)
    return text, final


def _fetch_apify(url: str) -> tuple[str, str]:
    token = (settings.apify_api_token or "").strip()
    actor = (settings.apify_actor_id or "").strip()
    if not token or not actor:
        raise WebFetchError(
            "Apify is selected (WEB_FETCH_PROVIDER=apify) but APIFY_API_TOKEN "
            "and APIFY_ACTOR_ID are not set. Use provider=direct, or configure Apify.",
            status_code=501,
        )
    raise WebFetchError(
        "Apify provider is reserved but not wired yet. Set WEB_FETCH_PROVIDER=direct "
        "or paste HTML for this page.",
        status_code=501,
    )


def _fetch_custom(url: str) -> tuple[str, str]:
    endpoint = (settings.web_fetch_api_url or "").strip()
    if not endpoint:
        raise WebFetchError(
            "Custom fetch is selected (WEB_FETCH_PROVIDER=custom) but "
            "WEB_FETCH_API_URL is empty.",
            status_code=501,
        )
    headers = {"Content-Type": "application/json"}
    if settings.web_fetch_api_key:
        headers["Authorization"] = f"Bearer {settings.web_fetch_api_key}"
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(endpoint, json={"url": url}, headers=headers)
    except httpx.HTTPError as exc:
        raise WebFetchError(f"Custom fetch API failed: {exc}", status_code=502) from exc
    if response.status_code >= 400:
        raise WebFetchError(
            f"Custom fetch API returned HTTP {response.status_code}",
            status_code=502,
        )
    payload = response.json()
    html = payload.get("html") or payload.get("content") or ""
    if not isinstance(html, str) or not html.strip():
        raise WebFetchError("Custom fetch API returned no html/content", status_code=502)
    return html, payload.get("finalUrl") or url


def fetch_web_page(url: str) -> tuple[str, str]:
    """Return (html_or_text, canonical_url) using the configured provider."""
    safe = validate_public_http_url(url)
    provider = (settings.web_fetch_provider or "direct").strip().lower()
    if provider == "direct":
        return _fetch_direct(safe)
    if provider == "apify":
        return _fetch_apify(safe)
    if provider == "custom":
        return _fetch_custom(safe)
    raise WebFetchError(
        f"Unknown WEB_FETCH_PROVIDER={provider!r}. Use direct, apify, or custom."
    )
