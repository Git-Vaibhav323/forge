from shared.utils import guess_doc_type, sanitize_filename


def test_sanitize_filename_strips_path() -> None:
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("") == "upload.bin"


def test_guess_doc_type() -> None:
    assert guess_doc_type("sheet.pdf") == "pdf"
    assert guess_doc_type("photo.jpg") == "image"
    assert guess_doc_type("catalog.csv") == "catalog"
    assert guess_doc_type("notes.txt") == "document"
