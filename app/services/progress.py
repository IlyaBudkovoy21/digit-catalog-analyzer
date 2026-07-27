import json
from datetime import datetime
from zoneinfo import ZoneInfo

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.db.models import DownloadRun


def progress_key(run_id: str) -> str:
    return f"download-run:{run_id}"


def serialize_run(run: DownloadRun) -> dict[str, object]:
    return {
        "id": run.id,
        "status": run.status,
        "started_at": _datetime_to_iso(run.started_at),
        "started_at_nsk": _datetime_to_nsk(run.started_at),
        "completed_at": _datetime_to_iso(run.completed_at),
        "total_names_received": run.total_names_received,
        "total_files_downloaded": run.total_files_downloaded,
        "last_message": run.last_message,
        "error": run.error,
    }


def save_progress(run: DownloadRun) -> None:
    try:
        client = Redis.from_url(get_settings().redis_url, decode_responses=True)
        client.setex(progress_key(run.id), 60 * 60 * 24, json.dumps(serialize_run(run), ensure_ascii=False))
    except RedisError:
        return


def load_progress(run_id: str) -> dict[str, object] | None:
    try:
        client = Redis.from_url(get_settings().redis_url, decode_responses=True)
        value = client.get(progress_key(run_id))
    except RedisError:
        return None
    if not value:
        return None
    return json.loads(value)


def _datetime_to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _datetime_to_nsk(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.astimezone(ZoneInfo("Asia/Novosibirsk")).isoformat()
