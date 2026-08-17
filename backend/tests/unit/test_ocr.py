from __future__ import annotations

import pytest

from shared.ocr import OcrError, clean_text, is_enabled, provider_name, read_image_text


# ---------------------------------------------------------------------------
# Post-processing must normalize, never reinterpret
# ---------------------------------------------------------------------------


def test_collapses_whitespace_and_drops_blank_lines():
    assert clean_text("Model:   MFC-GV-100  \n\n\n  Max   Pressure: 285 PSI ") == (
        "Model: MFC-GV-100\nMax Pressure: 285 PSI"
    )


def test_joins_words_broken_across_lines_by_a_hyphen():
    assert clean_text("MAX PRES-\nSURE: 285 PSI") == "MAX PRESSURE: 285 PSI"


def test_strips_control_characters():
    assert clean_text("Model:\x00 MFC-100\x07") == "Model: MFC-100"


def test_normalizes_unicode_punctuation_to_ascii():
    # An en-dash and a curly quote are the same characters in different
    # codepoints — swapping them cannot change a reading.
    assert clean_text("MFC–GV–100") == "MFC-GV-100"
    assert clean_text("Size: 2″") == 'Size: 2"'


def test_normalizes_line_endings():
    assert clean_text("A: 1\r\nB: 2\rC: 3") == "A: 1\nB: 2\nC: 3"


@pytest.mark.parametrize(
    "garbled",
    ["Max Pressure: 28S PSI", "Voltage: 24VDL", "Model: MFC-GV-1OO"],
)
def test_never_repairs_misread_characters(garbled: str):
    """The critical safety property of M7.

    OCR confuses S/5, O/0, C/L. "Fixing" those inside a value would fabricate a
    rating nobody can cite — exactly what this project exists to prevent. A
    misread stays misread, visible next to the photo it came from.
    """
    assert clean_text(garbled) == garbled


def test_empty_input_is_safe():
    assert clean_text("") == ""
    assert clean_text("   \n\n  ") == ""


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------


def test_off_is_the_default_and_reads_nothing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("shared.ocr.settings.ocr_provider", "off")
    assert provider_name() == "off"
    assert is_enabled() is False
    # Silence, not an exception: running without OCR is supported.
    assert read_image_text(b"\x89PNG fake bytes", filename="plate.png") == []


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("shared.ocr.settings.ocr_provider", "magic")
    with pytest.raises(OcrError, match="Unknown OCR_PROVIDER"):
        read_image_text(b"bytes", filename="plate.png")


def test_custom_provider_without_a_url_explains_itself(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("shared.ocr.settings.ocr_provider", "custom")
    monkeypatch.setattr("shared.ocr.settings.ocr_api_url", None)
    with pytest.raises(OcrError) as excinfo:
        read_image_text(b"bytes", filename="plate.png")
    assert excinfo.value.status_code == 501
    assert "OCR_API_URL" in str(excinfo.value)


def test_provider_output_is_cleaned_before_it_reaches_extraction(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("shared.ocr.settings.ocr_provider", "tesseract")
    monkeypatch.setattr(
        "shared.ocr._read_tesseract",
        lambda data: ["Model:   MFC-GV-100\n\n\nMax Pressure:  285 PSI"],
    )
    assert read_image_text(b"bytes", filename="plate.png") == [
        "Model: MFC-GV-100\nMax Pressure: 285 PSI"
    ]


def test_pages_that_clean_to_nothing_are_dropped(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("shared.ocr.settings.ocr_provider", "tesseract")
    monkeypatch.setattr("shared.ocr._read_tesseract", lambda data: ["   \n\n ", "Model: X"])
    assert read_image_text(b"bytes", filename="plate.png") == ["Model: X"]
