"""Sources API (SPEC section 4): list, create (website), upload (file), reindex, delete.

Every query filters by the caller's org; another org's source is a 404, never a 403.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import DbSession
from app.ingest import pipeline
from app.ingest.ssrf import UnsafeURLError, assert_public_url
from app.models import Source, new_id
from app.schemas import SourceCreate, SourceOut
from app.tenant import CurrentTenant, Tenant, WritableTenant

router = APIRouter(prefix="/sources", tags=["sources"])

IN_PROGRESS = frozenset({"queued", "crawling", "indexing"})
# First bytes of each allowed file type: the extension alone proves nothing.
MAGIC_BYTES = {".pdf": b"%PDF-", ".docx": b"PK\x03\x04"}
READ_CHUNK_BYTES = 1024 * 1024


def _get_source_or_404(db: Session, tenant: Tenant, source_id: str) -> Source:
    source = db.scalar(
        select(Source).where(Source.id == source_id, Source.organization_id == tenant.org)
    )
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    return source


@router.get("", response_model=list[SourceOut])
def list_sources(tenant: CurrentTenant, db: DbSession) -> list[Source]:
    """The caller's sources, newest first. Other orgs' sources are never visible."""
    stmt = (
        select(Source)
        .where(Source.organization_id == tenant.org)
        .order_by(Source.created_at.desc(), Source.id.desc())
    )
    return list(db.scalars(stmt))


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(
    body: SourceCreate, tenant: WritableTenant, db: DbSession, tasks: BackgroundTasks
) -> Source:
    """Register a website and crawl it in the background. Returns at once with status `queued`."""
    url = str(body.location)
    try:
        assert_public_url(url)  # fail fast with a clear 400; the crawler re-checks every hop
    except UnsafeURLError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"URL not allowed: {exc}") from None

    source = Source(
        organization_id=tenant.org,
        kind="website",
        label=body.label or (urlsplit(url).hostname or url)[:200],
        location=url,
    )
    db.add(source)
    db.commit()
    tasks.add_task(pipeline.run_ingestion, source.id, tenant.org)
    return source


def _read_limited(file: UploadFile, limit: int) -> bytes:
    """Read at most `limit` bytes; stop early instead of buffering a huge upload."""
    data = bytearray()
    while piece := file.file.read(READ_CHUNK_BYTES):
        data.extend(piece)
        if len(data) > limit:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"File is larger than {limit // (1024 * 1024)} MB"
            )
    return bytes(data)


def _validate_upload(name: str, data: bytes) -> str:
    extension = Path(name).suffix.lower()
    if extension not in settings.upload_allowed_extensions:
        allowed = ", ".join(settings.upload_allowed_extensions)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported file type. Allowed: {allowed}")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is empty")
    magic = MAGIC_BYTES.get(extension)
    if magic is not None and not data.startswith(magic):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"File content is not a valid {extension}")
    if magic is None:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Text files must be UTF-8") from None
    return extension


@router.post("/upload", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def upload_source(
    file: UploadFile, tenant: WritableTenant, db: DbSession, tasks: BackgroundTasks
) -> Source:
    """Upload a PDF, DOCX, TXT or MD file (max 10 MB) and index it in the background.

    A plain `def`, not `async def`: it does blocking file and DB work, so FastAPI runs it
    in the thread pool instead of blocking the event loop.
    """
    original_name = Path(file.filename or "upload").name[:200]  # drop any client-sent directories
    data = _read_limited(file, settings.upload_max_bytes)
    extension = _validate_upload(original_name, data)

    source = Source(
        id=new_id("src"),
        organization_id=tenant.org,
        kind="text" if extension in (".txt", ".md") else extension.lstrip("."),
        label=original_name,
        location=original_name,
    )
    path = pipeline.upload_path(source)  # <source id><ext>: random, never the client's name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    db.add(source)
    db.commit()
    tasks.add_task(pipeline.run_ingestion, source.id, tenant.org)
    return source


@router.post("/{source_id}/reindex", response_model=SourceOut)
def reindex_source(
    source_id: str, tenant: WritableTenant, db: DbSession, tasks: BackgroundTasks
) -> Source:
    """Queue a fresh ingestion. Old chunks are replaced, not appended to."""
    source = _get_source_or_404(db, tenant, source_id)
    if source.status in IN_PROGRESS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Source is already being indexed")
    source.status, source.error = "queued", None
    db.commit()
    tasks.add_task(pipeline.run_ingestion, source.id, tenant.org)
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: str, tenant: WritableTenant, db: DbSession) -> Response:
    """Delete the source, its chunks and their vectors (one SQL cascade) and any uploaded file."""
    source = _get_source_or_404(db, tenant, source_id)
    if source.kind != "website":
        pipeline.upload_path(source).unlink(missing_ok=True)
    db.delete(source)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
