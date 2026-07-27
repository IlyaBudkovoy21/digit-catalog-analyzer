import hashlib
import time
from datetime import timezone
from pathlib import PurePath

from celery.utils.log import get_task_logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import DownloadRun, DownloadedFile, utc_now
from app.db.session import SessionLocal, init_db
from app.services.file_api_client import FileApiClient, FileApiError, RateLimitError
from app.services.progress import save_progress
from app.services.stats import count_digit_stats
from app.services.zip_reader import extract_text_files
from app.tasks.celery_app import celery_app


logger = get_task_logger(__name__)


@celery_app.task(name="download_catalog")
def download_catalog(run_id: str, api_base_url: str | None = None, candidate_id: str | None = None) -> dict[str, str]:
    init_db()
    settings = get_settings()
    db = SessionLocal()
    client = FileApiClient(
        base_url=api_base_url or settings.external_api_base_url,
        candidate_id=candidate_id if candidate_id is not None else settings.candidate_id,
        timeout_seconds=settings.request_timeout_seconds,
    )
    try:
        run = _get_run(db, run_id)
        run.status = "running"
        run.started_at = utc_now()
        run.last_message = "Процесс скачивания запущен"
        _commit_progress(db, run)

        while True:
            names = _call_with_rate_limit(db, run, client.get_names)
            run.total_names_received += len(names)

            if not names:
                run.status = "completed"
                run.completed_at = utc_now()
                run.last_message = "Каталог скачан полностью"
                _commit_progress(db, run)
                return {"status": "completed"}

            run.last_message = f"Получено {len(names)} названий файлов"
            _commit_progress(db, run)

            for batch in _chunks(names, settings.max_download_batch_size):
                archive = _call_with_rate_limit(db, run, lambda batch=batch: client.download(batch))
                extracted = extract_text_files(archive)
                saved_names = _save_extracted_files(db, extracted, batch)

                _call_with_rate_limit(db, run, lambda batch=batch: client.mark_downloaded(batch))
                run.total_files_downloaded += len(batch)
                run.last_message = f"Скачано {run.total_files_downloaded} из {run.total_names_received} полученных названий"
                _commit_progress(db, run)
                logger.info("saved files from batch: %s", saved_names)
    except Exception as exc:
        run = _get_run(db, run_id)
        run.status = "failed"
        run.completed_at = utc_now()
        run.error = str(exc)
        run.last_message = "Процесс завершился ошибкой"
        _commit_progress(db, run)
        raise
    finally:
        client.close()
        db.close()


def _get_run(db: Session, run_id: str) -> DownloadRun:
    run = db.get(DownloadRun, run_id)
    if not run:
        raise FileApiError(f"download run {run_id} was not found")
    return run


def _call_with_rate_limit(db: Session, run: DownloadRun, call):
    while True:
        try:
            if run.status == "waiting":
                run.status = "running"
                _commit_progress(db, run)
            return call()
        except RateLimitError as exc:
            run.status = "waiting"
            run.last_message = f"Лимит API: пауза {exc.retry_after_seconds} секунд после ответа {exc.status_code}"
            _commit_progress(db, run)
            time.sleep(exc.retry_after_seconds)


def _save_extracted_files(db: Session, extracted: dict[str, str], requested_names: list[str]) -> list[str]:
    saved_names: list[str] = []
    for requested_name in requested_names:
        content = _match_content(extracted, requested_name)
        if content is None:
            raise FileApiError(f"zip archive does not contain requested file: {requested_name}")

        file = DownloadedFile(
            name=requested_name,
            content=content,
            downloaded_at=utc_now().astimezone(timezone.utc),
            size_bytes=len(content.encode("utf-8")),
            sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            digit_stats=count_digit_stats(content),
        )
        db.add(file)
        try:
            db.commit()
            saved_names.append(requested_name)
        except IntegrityError:
            db.rollback()
    return saved_names


def _match_content(extracted: dict[str, str], requested_name: str) -> str | None:
    if requested_name in extracted:
        return extracted[requested_name]

    requested_basename = PurePath(requested_name).name
    for zip_name, content in extracted.items():
        if PurePath(zip_name).name == requested_basename:
            return content
    return None


def _commit_progress(db: Session, run: DownloadRun) -> None:
    db.commit()
    db.refresh(run)
    save_progress(run)


def _chunks(items: list[str], size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]
