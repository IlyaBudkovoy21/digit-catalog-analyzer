from io import BytesIO
from zipfile import ZipFile

from app.services.zip_reader import extract_text_files


def test_extract_text_files_from_zip() -> None:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("a.txt", "12345\n")
        archive.writestr("nested/b.txt", "999")

    assert extract_text_files(buffer.getvalue()) == {"a.txt": "12345", "nested/b.txt": "999"}
