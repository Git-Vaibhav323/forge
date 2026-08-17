from __future__ import annotations

import pytest

from services.file_service.web_fetch import WebFetchError, validate_public_http_url
from shared.html_text import html_to_text


def test_html_to_text_strips_tags_and_scripts() -> None:
    html = """
    <html><head><script>evil()</script><style>.x{}</style></head>
    <body>
      <h1>Meridian Flow Controls</h1>
      <p>Model: MFC-GV-100</p>
      <p>Max Working Pressure: 285 PSI</p>
    </body></html>
    """
    text = html_to_text(html)
    assert "evil" not in text
    assert "Model: MFC-GV-100" in text
    assert "285 PSI" in text
    assert "Meridian Flow Controls" in text


def test_validate_rejects_non_http() -> None:
    with pytest.raises(WebFetchError):
        validate_public_http_url("ftp://example.com/x", resolve_host=False)


def test_validate_accepts_public_shape_without_resolve() -> None:
    assert (
        validate_public_http_url("https://catalog.example.com/valve", resolve_host=False)
        == "https://catalog.example.com/valve"
    )
