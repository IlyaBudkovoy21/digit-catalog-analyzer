from contextlib import asynccontextmanager
from math import ceil
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import DownloadRun, DownloadedFile
from app.db.session import get_db, init_db
from app.services.progress import load_progress, serialize_run
from app.services.stats import count_digit_stats, merge_digit_stats
from app.tasks.download import download_catalog


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Digit Catalog Analyzer", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
templates = Jinja2Templates(directory="app/web/templates")


class DownloadStartRequest(BaseModel):
    api_base_url: str | None = None
    candidate_id: str | None = None


class CalculateRequest(BaseModel):
    file_ids: list[int] = Field(default_factory=list)
    all_files: bool = False


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def download_page(request: Request) -> HTMLResponse:
    settings = get_settings()
    return templates.TemplateResponse(
        "download.html",
        {
            "request": request,
            "external_api_base_url": settings.external_api_base_url,
            "candidate_id": settings.candidate_id,
        },
    )


@app.get("/files", response_class=HTMLResponse)
def files_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("files.html", {"request": request})


@app.post("/api/download/start")
def start_download(payload: DownloadStartRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    settings = get_settings()
    api_base_url = (payload.api_base_url or settings.external_api_base_url).strip()
    if not api_base_url:
        raise HTTPException(status_code=400, detail="Set EXTERNAL_API_BASE_URL or provide api_base_url")

    run = DownloadRun(id=str(uuid4()), status="queued", last_message="Задача поставлена в очередь")
    db.add(run)
    db.commit()
    db.refresh(run)

    download_catalog.delay(run.id, api_base_url, payload.candidate_id)
    return serialize_run(run)


@app.get("/api/download/runs/latest")
def latest_download_run(db: Session = Depends(get_db)) -> dict[str, object] | None:
    run = db.scalars(select(DownloadRun).order_by(desc(DownloadRun.created_at)).limit(1)).first()
    return serialize_run(run) if run else None


@app.get("/api/download/runs/{run_id}")
def download_run(run_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    cached = load_progress(run_id)
    if cached:
        return cached
    run = db.get(DownloadRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Download run not found")
    return serialize_run(run)


@app.get("/api/files")
def list_files(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    total = db.scalar(select(func.count()).select_from(DownloadedFile)) or 0
    order_by = asc(DownloadedFile.downloaded_at) if order == "asc" else desc(DownloadedFile.downloaded_at)
    files = db.scalars(
        select(DownloadedFile)
        .order_by(order_by, DownloadedFile.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "items": [
            {
                "id": file.id,
                "name": file.name,
                "downloaded_at": file.downloaded_at.isoformat(),
                "size_bytes": file.size_bytes,
                "sha256": file.sha256,
            }
            for file in files
        ],
        "page": page,
        "page_size": page_size,
        "pages": max(1, ceil(total / page_size)) if total else 1,
        "total": total,
    }


@app.post("/api/files/calculate")
def calculate(payload: CalculateRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    if payload.all_files:
        query = select(DownloadedFile).order_by(desc(DownloadedFile.downloaded_at), DownloadedFile.id)
    else:
        if not payload.file_ids:
            raise HTTPException(status_code=400, detail="Select at least one file")
        query = (
            select(DownloadedFile)
            .where(DownloadedFile.id.in_(payload.file_ids))
            .order_by(desc(DownloadedFile.downloaded_at), DownloadedFile.id)
        )

    files = db.scalars(query).all()
    per_file: list[dict[str, object]] = []
    stats_items: list[dict[str, int]] = []

    for file in files:
        stats = file.digit_stats or count_digit_stats(file.content)
        if file.digit_stats is None:
            file.digit_stats = stats
        stats_items.append(stats)
        per_file.append({"id": file.id, "name": file.name, "downloaded_at": file.downloaded_at.isoformat(), "stats": stats})

    db.commit()
    return {
        "selected_count": len(files),
        "total_stats": merge_digit_stats(stats_items),
        "files": per_file,
    }
