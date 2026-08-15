from shared.utils import guess_doc_type, sanitize_filename
from services.file_service.storage import _endpoint_url


def test_sanitize_filename_strips_path() -> None:
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("") == "upload.bin"


def test_guess_doc_type() -> None:
    assert guess_doc_type("sheet.pdf") == "pdf"
    assert guess_doc_type("photo.jpg") == "image"
    assert guess_doc_type("catalog.csv") == "catalog"
    assert guess_doc_type("notes.txt") == "document"


def test_endpoint_url_minio_and_supabase(monkeypatch) -> None:
    from services.file_service import storage as storage_mod

    monkeypatch.setattr(storage_mod.settings, "object_storage_endpoint", "localhost:9000")
    monkeypatch.setattr(storage_mod.settings, "object_storage_secure", False)
    assert _endpoint_url() == "http://localhost:9000"

    monkeypatch.setattr(
        storage_mod.settings,
        "object_storage_endpoint",
        "abcdefghijklmnop.storage.supabase.co",
    )
    assert _endpoint_url() == "https://abcdefghijklmnop.storage.supabase.co/storage/v1/s3"

    monkeypatch.setattr(
        storage_mod.settings,
        "object_storage_endpoint",
        "https://abcdefghijklmnop.storage.supabase.co/storage/v1/s3",
    )
    assert _endpoint_url() == "https://abcdefghijklmnop.storage.supabase.co/storage/v1/s3"


def test_sanitize_filename_strips_path() -> None:
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("") == "upload.bin"


def test_guess_doc_type() -> None:
    assert guess_doc_type("sheet.pdf") == "pdf"
    assert guess_doc_type("photo.jpg") == "image"
    assert guess_doc_type("catalog.csv") == "catalog"
    assert guess_doc_type("notes.txt") == "document"
