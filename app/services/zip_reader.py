from io import BytesIO
from zipfile import BadZipFile, ZipFile


class ZipReadError(RuntimeError):
    pass


def extract_text_files(archive_bytes: bytes) -> dict[str, str]:
    try:
        with ZipFile(BytesIO(archive_bytes)) as archive:
            result: dict[str, str] = {}
            for member in archive.infolist():
                if member.is_dir():
                    continue
                with archive.open(member) as file:
                    result[member.filename] = file.read().decode("utf-8").strip()
            return result
    except (BadZipFile, UnicodeDecodeError) as exc:
        raise ZipReadError("download endpoint returned an invalid zip archive") from exc
