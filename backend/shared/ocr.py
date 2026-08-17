"""Read text off a nameplate photo or scanned page (M7).

Providers (OCR_PROVIDER), mirroring `file_service/web_fetch.py`:

  off        — default. Returns no text at all. Images are still stored and
               still listed on the job; they simply contribute no facts.
  tesseract  — local pytesseract + Pillow. Needs the tesseract binary.
  ocrspace   — OCR.space cloud API (OCR_API_KEY from ocr.space).
  custom     — POST the image to OCR_API_URL; expects {text} or {pages}.

**Off is a real answer, not a failure.** The stack must run on a clean machine
with no system binaries, so an unreadable image produces silence rather than an
error — and silence produces `missing`, never a guess.

## Why post-processing never "corrects" characters

OCR confuses O/0, I/1, S/5, B/8. Repairing those inside a *value* would be
invention of exactly the kind this project exists to prevent: turning a blurry
"28S PSI" into "285 PSI" fabricates a pressure rating nobody can cite.
`clean_text` therefore only performs changes that cannot alter meaning —
whitespace, control characters, unicode punctuation, and hyphen-broken line
joins. A misread character stays misread, and the human sees it next to the
photo it came from.
"""

from __future__ import annotations

import re
import unicodedata

from app.config import settings
from shared.utils import IMAGE_DOC_TYPES  # noqa: F401 — re-exported for callers


class OcrError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Post-processing — meaning-preserving only
# ---------------------------------------------------------------------------

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# A word broken across lines by a trailing hyphen: "PRES-\nSURE" → "PRESSURE".
_HYPHEN_BREAK = re.compile(r"(\w)-[ \t]*\n[ \t]*(\w)")
_MULTISPACE = re.compile(r"[ \t ]+")

# Unicode punctuation that OCR emits for plain ASCII. Substituting these cannot
# change a reading — they are the same character in a different codepoint.
_PUNCTUATION = {
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "°": "°", "″": '"', "′": "'",
    "：": ":", "，": ",", "．": ".",
}


def clean_text(raw: str) -> str:
    """Normalize OCR output without changing what it says."""
    if not raw:
        return ""

    # Punctuation is mapped BEFORE NFKC: NFKC decomposes ″ (double prime) into
    # two apostrophes, which would destroy the inch symbol that the
    # nominal_size rule matches on.
    text = raw
    for source, target in _PUNCTUATION.items():
        text = text.replace(source, target)
    text = unicodedata.normalize("NFKC", text)

    text = _CONTROL.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHEN_BREAK.sub(r"\1\2", text)

    lines = [_MULTISPACE.sub(" ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


def _read_tesseract(data: bytes) -> list[str]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise OcrError(
            "OCR_PROVIDER=tesseract but pytesseract/Pillow are not installed. "
            "Run: python -m pip install pytesseract pillow (and install the "
            "tesseract binary), or set OCR_PROVIDER=off.",
            status_code=501,
        ) from exc

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    from io import BytesIO

    try:
        with Image.open(BytesIO(data)) as image:
            text = pytesseract.image_to_string(image)
    except Exception as exc:
        raise OcrError(f"Could not read the image: {exc}", status_code=502) from exc
    return [text]


OCRSPACE_URL = "https://api.ocr.space/parse/image"


def _read_ocrspace(data: bytes, filename: str) -> list[str]:
    api_key = (settings.ocr_api_key or "").strip()
    if not api_key:
        raise OcrError(
            "OCR_PROVIDER=ocrspace but OCR_API_KEY is empty.", status_code=501
        )

    import httpx

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                OCRSPACE_URL,
                data={"apikey": api_key, "language": "eng", "OCREngine": "2"},
                files={"file": (filename or "image", data)},
            )
    except Exception as exc:
        raise OcrError(f"OCR.space API failed: {exc}", status_code=502) from exc

    if response.status_code >= 400:
        raise OcrError(
            f"OCR.space returned HTTP {response.status_code}", status_code=502
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise OcrError("OCR.space returned a non-JSON response", status_code=502) from exc
    if not isinstance(payload, dict):
        raise OcrError("OCR.space returned an unexpected payload", status_code=502)
    if payload.get("IsErroredOnProcessing"):
        raw_message = payload.get("ErrorMessage") or "processing failed"
        if isinstance(raw_message, list):
            raw_message = "; ".join(str(part) for part in raw_message)
        raise OcrError(f"OCR.space error: {raw_message}", status_code=502)

    results = payload.get("ParsedResults") or []
    pages: list[str] = []
    for item in results:
        if isinstance(item, dict):
            text = item.get("ParsedText") or ""
            if isinstance(text, str) and text.strip():
                pages.append(text)
    if not pages:
        raise OcrError("OCR.space returned no text", status_code=502)
    return pages


def _read_custom(data: bytes, filename: str) -> list[str]:
    endpoint = (settings.ocr_api_url or "").strip()
    if not endpoint:
        raise OcrError(
            "OCR_PROVIDER=custom but OCR_API_URL is empty.", status_code=501
        )

    import httpx

    headers = {}
    if settings.ocr_api_key:
        headers["Authorization"] = f"Bearer {settings.ocr_api_key}"

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                endpoint,
                files={"file": (filename or "image", data)},
                headers=headers,
            )
    except Exception as exc:
        raise OcrError(f"OCR API failed: {exc}", status_code=502) from exc

    if response.status_code >= 400:
        raise OcrError(
            f"OCR API returned HTTP {response.status_code}", status_code=502
        )

    payload = response.json()
    pages = payload.get("pages")
    if isinstance(pages, list) and pages:
        return [str(page) for page in pages]
    text = payload.get("text") or ""
    if not isinstance(text, str) or not text.strip():
        raise OcrError("OCR API returned no text", status_code=502)
    return [text]


def provider_name() -> str:
    return (settings.ocr_provider or "off").strip().lower()


def is_enabled() -> bool:
    return provider_name() != "off"


def read_image_text(data: bytes, *, filename: str = "image") -> list[str]:
    """Return page texts for an image. Empty list when OCR is off."""
    provider = provider_name()
    if provider == "off":
        return []

    if provider == "tesseract":
        pages = _read_tesseract(data)
    elif provider == "ocrspace":
        pages = _read_ocrspace(data, filename)
    elif provider == "custom":
        pages = _read_custom(data, filename)
    else:
        raise OcrError(
            f"Unknown OCR_PROVIDER={provider!r}. Use off, tesseract, ocrspace, or custom."
        )

    cleaned = [clean_text(page) for page in pages]
    return [page for page in cleaned if page]
