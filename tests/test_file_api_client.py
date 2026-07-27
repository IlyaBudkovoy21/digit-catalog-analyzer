from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from app.services.file_api_client import _retry_after_seconds


def test_retry_after_seconds_from_number() -> None:
    assert _retry_after_seconds("12", 429) == 12


def test_retry_after_seconds_from_http_date() -> None:
    retry_at = datetime.now(timezone.utc) + timedelta(seconds=60)

    assert 1 <= _retry_after_seconds(format_datetime(retry_at), 429) <= 60


def test_retry_after_seconds_has_block_default_for_403() -> None:
    assert _retry_after_seconds(None, 403) == 1800
