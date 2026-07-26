"""OpenAPI tool server exposing Paperless-ngx to Open WebUI.

Paperless-ngx's built-in chat retrieves at most 5 vector chunks, which is fine
for "what is this document" but cannot answer questions that need the whole
corpus ("list every X", "how many Y"). These tools hand the model complete
query results from the Paperless API instead, and let it write a real CSV.
"""

import csv
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic import Field

PAPERLESS_URL = os.environ.get("PAPERLESS_URL", "http://paperless:8000").rstrip("/")
PAPERLESS_TOKEN = os.environ.get("PAPERLESS_TOKEN", "")
EXPORT_DIR = Path(os.environ.get("EXPORT_DIR", "/export"))
# Keep tool output inside the model's context window. llama-cpp runs 8192
# tokens per slot, so ~24k characters of document text is already generous.
MAX_CONTENT_CHARS = int(os.environ.get("MAX_CONTENT_CHARS", "24000"))
MAX_SEARCH_RESULTS = int(os.environ.get("MAX_SEARCH_RESULTS", "50"))
PREVIEW_ROWS = 10

app = FastAPI(
    title="Paperless Tools",
    version="1.0.0",
    description=(
        "Search and read documents in Paperless-ngx, and export tabular "
        "results to CSV files."
    ),
)


def _client() -> httpx.Client:
    if not PAPERLESS_TOKEN:
        raise HTTPException(500, "PAPERLESS_TOKEN is not set on the tool server")
    return httpx.Client(
        base_url=PAPERLESS_URL,
        headers={
            "Authorization": f"Token {PAPERLESS_TOKEN}",
            "Accept": "application/json",
        },
        timeout=60.0,
    )


class SearchRequest(BaseModel):
    query: str = Field(
        description=(
            "Full-text search query. Matches document text, title and notes. "
            "Supports quoted phrases for exact matches, e.g. '\"Edward A. Cruz\"'. "
            "This is a keyword search, so use the literal words expected to "
            "appear in the document rather than a natural-language question."
        ),
    )
    limit: int = Field(
        default=25,
        ge=1,
        le=MAX_SEARCH_RESULTS,
        description="Maximum number of documents to return.",
    )


class SearchResult(BaseModel):
    document_id: int
    title: str
    created: str | None = None
    correspondent: str | None = None
    document_type: str | None = None
    tags: list[str] = []


class SearchResponse(BaseModel):
    result_count: int
    truncated: bool = Field(
        description="True when more documents matched than were returned.",
    )
    results: list[SearchResult]


@app.post(
    "/search_documents",
    operation_id="search_documents",
    summary="Search documents by keyword",
    response_model=SearchResponse,
)
def search_documents(request: SearchRequest) -> SearchResponse:
    """Find documents whose text, title or notes match a keyword query.

    Returns every match up to the limit, not a similarity-ranked sample, so the
    result count can be trusted for questions like "how many documents mention
    X". Use this to locate documents, then call get_document_content to read
    them.
    """
    with _client() as client:
        names = _lookup_names(client)
        response = client.get(
            "/api/documents/",
            params={
                "query": request.query,
                "page_size": request.limit,
                "ordering": "-created",
            },
        )
        if response.status_code != 200:
            raise HTTPException(
                response.status_code,
                f"Paperless search failed: {response.text[:200]}",
            )
        payload = response.json()

    results = [
        SearchResult(
            document_id=doc["id"],
            title=doc.get("title") or "",
            created=(doc.get("created") or "")[:10] or None,
            correspondent=names["correspondents"].get(doc.get("correspondent")),
            document_type=names["document_types"].get(doc.get("document_type")),
            tags=[names["tags"][t] for t in doc.get("tags", []) if t in names["tags"]],
        )
        for doc in payload.get("results", [])
    ]
    total = payload.get("count", len(results))
    return SearchResponse(
        result_count=total,
        truncated=total > len(results),
        results=results,
    )


class ContentRequest(BaseModel):
    document_id: int = Field(
        description="The id of the document to read, as returned by search_documents.",
    )


class ContentResponse(BaseModel):
    document_id: int
    title: str
    created: str | None = None
    content: str
    truncated: bool = Field(
        description="True when the text was cut short to fit the context window.",
    )


@app.post(
    "/get_document_content",
    operation_id="get_document_content",
    summary="Read the full text of one document",
    response_model=ContentResponse,
)
def get_document_content(request: ContentRequest) -> ContentResponse:
    """Return the complete OCR text of a single document.

    Read documents one at a time. Reading many long documents in one
    conversation will overflow the model's context window.
    """
    with _client() as client:
        response = client.get(f"/api/documents/{request.document_id}/")
        if response.status_code == 404:
            raise HTTPException(404, f"No document with id {request.document_id}")
        if response.status_code != 200:
            raise HTTPException(
                response.status_code,
                f"Paperless request failed: {response.text[:200]}",
            )
        doc = response.json()

    content = doc.get("content") or ""
    truncated = len(content) > MAX_CONTENT_CHARS
    return ContentResponse(
        document_id=doc["id"],
        title=doc.get("title") or "",
        created=(doc.get("created") or "")[:10] or None,
        content=content[:MAX_CONTENT_CHARS],
        truncated=truncated,
    )


class ExportRequest(BaseModel):
    filename: str = Field(
        description=(
            "Base name for the CSV file, without a directory. A .csv suffix and "
            "a timestamp are added automatically, e.g. 'baptisms'."
        ),
    )
    columns: list[str] = Field(
        description="Column headers, in the order they should appear.",
    )
    rows: list[dict[str, Any]] = Field(
        description=(
            "One object per row, keyed by column header. Missing keys become "
            "empty cells."
        ),
    )


class ExportResponse(BaseModel):
    file: str
    row_count: int
    columns: list[str]
    preview: list[dict[str, Any]] = Field(
        description="The first rows written, for showing the user in chat.",
    )
    message: str


@app.post(
    "/export_csv",
    operation_id="export_csv",
    summary="Write rows to a CSV file",
    response_model=ExportResponse,
)
def export_csv(request: ExportRequest) -> ExportResponse:
    """Write tabular data to a CSV file in the Paperless export directory.

    Call this after gathering the data with the other tools. Pass the rows you
    assembled; this tool does not query Paperless itself.
    """
    if not request.columns:
        raise HTTPException(400, "columns must not be empty")
    if not request.rows:
        raise HTTPException(400, "rows must not be empty")

    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(request.filename).stem).strip("-")
    if not stem:
        stem = "export"
    name = f"{stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    target = EXPORT_DIR / name

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=request.columns,
            extrasaction="ignore",
            restval="",
        )
        writer.writeheader()
        for row in request.rows:
            writer.writerow({k: _sanitize(v) for k, v in row.items()})

    return ExportResponse(
        file=name,
        row_count=len(request.rows),
        columns=request.columns,
        preview=request.rows[:PREVIEW_ROWS],
        message=(
            f"Wrote {len(request.rows)} rows to {name} in the Paperless export "
            f"directory. Show the user the preview rows and tell them the filename."
        ),
    )


def _sanitize(value: Any) -> Any:
    """Defuse spreadsheet formula injection in exported cells."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _lookup_names(client: httpx.Client) -> dict[str, dict[int, str]]:
    """Fetch id -> name maps so results carry readable labels."""
    lookups: dict[str, dict[int, str]] = {}
    for key in ("correspondents", "document_types", "tags"):
        try:
            response = client.get(f"/api/{key}/", params={"page_size": 1000})
            response.raise_for_status()
            lookups[key] = {i["id"]: i["name"] for i in response.json()["results"]}
        except (httpx.HTTPError, KeyError):
            # Labels are cosmetic; a failed lookup should not fail the search.
            lookups[key] = {}
    return lookups


# Excluded from the OpenAPI schema on purpose: Open WebUI turns every
# advertised operation into a tool the model can pick, and a liveness probe is
# only noise in that list.
@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    """Report whether the tool server can reach Paperless."""
    try:
        with _client() as client:
            response = client.get("/api/documents/", params={"page_size": 1})
        reachable = response.status_code == 200
    except (httpx.HTTPError, HTTPException):
        reachable = False
    return {
        "status": "ok" if reachable else "degraded",
        "paperless": PAPERLESS_URL,
        "export_dir": str(EXPORT_DIR),
    }
