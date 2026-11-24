"""The sources API end to end: background ingestion, validation, tenant isolation."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import vector_store
from app.config import settings
from app.ingest import crawler, ssrf
from app.ingest.crawler import Page
from app.models import Chunk
from tests.tokens import auth_header

TEXT = " ".join(f"word{i}" for i in range(40))
A, B = auth_header(org="org_a"), auth_header(org="org_b")


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fake DNS and crawler, and a temporary upload folder."""
    monkeypatch.setattr(
        ssrf, "_resolve", lambda host, _port: ["93.184.216.34"] if "example" in host else [host]
    )
    monkeypatch.setattr(
        crawler, "crawl", lambda url: [Page(url, "Home", f"<h1>Start</h1><p>{TEXT}</p>")]
    )
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))


def upload(client: TestClient, name: str, data: bytes, headers: dict[str, str] = A):
    return client.post("/api/sources/upload", headers=headers, files={"file": (name, io.BytesIO(data))})


# --- Create (website) -----------------------------------------------------------------------


def test_create_website_returns_201_queued_then_becomes_ready(client: TestClient) -> None:
    res = client.post("/api/sources", headers=A, json={"kind": "website", "location": "https://docs.example.com"})
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "queued" and body["label"] == "docs.example.com"

    # TestClient runs background tasks before returning, so ingestion has finished by now.
    [listed] = client.get("/api/sources", headers=A).json()
    assert listed["status"] == "ready" and listed["chunkCount"] == 1 and listed["pageCount"] == 1


def test_create_rejects_internal_url_with_400(client: TestClient) -> None:
    res = client.post("/api/sources", headers=A, json={"kind": "website", "location": "http://127.0.0.1:8000"})
    assert res.status_code == 400
    assert "not allowed" in res.json()["detail"]


def test_create_rejects_client_sent_org_with_422(client: TestClient) -> None:
    res = client.post(
        "/api/sources",
        headers=A,
        json={"kind": "website", "location": "https://docs.example.com", "organizationId": "org_b"},
    )
    assert res.status_code == 422


def test_create_requires_token(client: TestClient) -> None:
    res = client.post("/api/sources", json={"kind": "website", "location": "https://docs.example.com"})
    assert res.status_code == 401


# --- Upload ---------------------------------------------------------------------------------


def test_upload_text_file_is_stored_under_random_name_and_indexed(client: TestClient) -> None:
    res = upload(client, "../../etc/notes.md", TEXT.encode())
    assert res.status_code == 201
    body = res.json()
    assert body["label"] == "notes.md"  # directories from the client are dropped

    stored = list(Path(settings.upload_dir).iterdir())
    assert [p.name for p in stored] == [f"{body['id']}.md"]  # not the client's file name
    assert client.get("/api/sources", headers=A).json()[0]["status"] == "ready"


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        ("virus.exe", b"MZ...", "Unsupported file type"),
        ("fake.pdf", b"<html>not a pdf</html>", "not a valid .pdf"),
        ("fake.docx", b"plain text", "not a valid .docx"),
        ("latin1.txt", "café".encode("latin-1"), "UTF-8"),
        ("empty.txt", b"", "empty"),
    ],
)
def test_upload_rejects_bad_files(client: TestClient, name: str, data: bytes, message: str) -> None:
    res = upload(client, name, data)
    assert res.status_code == 400
    assert message in res.json()["detail"]


def test_upload_rejects_files_over_the_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "upload_max_bytes", 100)
    res = upload(client, "big.txt", b"x" * 101)
    assert res.status_code == 400 and "larger than" in res.json()["detail"]


# --- Reindex and delete ---------------------------------------------------------------------


def _create(client: TestClient, headers: dict[str, str] = A) -> str:
    res = client.post("/api/sources", headers=headers, json={"kind": "website", "location": "https://docs.example.com"})
    return str(res.json()["id"])


def test_reindex_returns_200_and_replaces_chunks(client: TestClient, db: Session) -> None:
    source_id = _create(client)
    res = client.post(f"/api/sources/{source_id}/reindex", headers=A)
    assert res.status_code == 200
    assert len(db.scalars(select(Chunk)).all()) == 1  # replaced, not appended


def test_reindex_while_in_progress_is_409(client: TestClient, db: Session) -> None:
    source_id = _create(client)
    from app.models import Source

    db.get(Source, source_id).status = "crawling"  # type: ignore[union-attr]
    db.commit()
    assert client.post(f"/api/sources/{source_id}/reindex", headers=A).status_code == 409


def test_delete_removes_source_chunks_vectors_and_file(client: TestClient, db: Session) -> None:
    source_id = upload(client, "notes.txt", TEXT.encode()).json()["id"]
    assert vector_store.count() == 1

    assert client.delete(f"/api/sources/{source_id}", headers=A).status_code == 204
    assert client.get("/api/sources", headers=A).json() == []
    assert db.scalars(select(Chunk)).all() == []
    assert vector_store.count() == 0
    assert list(Path(settings.upload_dir).iterdir()) == []


@pytest.mark.parametrize("action", ["reindex", "delete"])
def test_another_orgs_source_is_404(client: TestClient, action: str) -> None:
    source_id = _create(client, headers=A)
    if action == "reindex":
        res = client.post(f"/api/sources/{source_id}/reindex", headers=B)
    else:
        res = client.delete(f"/api/sources/{source_id}", headers=B)
    assert res.status_code == 404  # not 403: org B can't even learn that it exists
    assert len(client.get("/api/sources", headers=A).json()) == 1  # untouched
