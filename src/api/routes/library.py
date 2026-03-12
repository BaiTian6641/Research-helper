"""GET/POST /api/v1/library — local-library management."""

from __future__ import annotations

import io
import logging
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from src.api import schemas
import src.api.main as _main

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/library", response_model=List[schemas.LibraryPaperResponse])
async def list_library(
    search: Optional[str] = Query(None, description="Keyword filter"),
):
    """List or search papers in the local library."""
    library_store = _main.library_store
    if library_store is None:
        raise HTTPException(503, "Library store not ready")
    if search:
        papers = library_store.search_papers(search)
    else:
        papers = library_store.get_all_papers()

    return [
        schemas.LibraryPaperResponse(
            id=p.id,
            title=p.title,
            authors=p.get_authors(),
            year=p.year,
            venue=p.venue,
            abstract=p.abstract,
            citations=p.citations,
            doi=p.doi,
            url=p.url,
            file_path=getattr(p, "file_path", None),
        )
        for p in papers
    ]


@router.post("/library/upload")
async def upload_to_library(file: UploadFile = File(...)):
    """Upload a BibTeX, RIS, or CSV file to the local library."""
    library_store = _main.library_store
    if library_store is None:
        raise HTTPException(503, "Library store not ready")

    suffix = (file.filename or "").rsplit(".", 1)[-1].lower()
    if suffix not in ("bib", "ris", "csv"):
        raise HTTPException(
            400, "Unsupported file type. Upload .bib, .ris, or .csv files."
        )

    raw = await file.read()
    text = raw.decode("utf-8", errors="replace")

    from src.ingestion.ingestion_service import IngestionService

    svc = IngestionService()
    papers = svc.parse_text(text, fmt=suffix)

    if not papers:
        raise HTTPException(400, "Could not parse any papers from the uploaded file.")

    added = library_store.add_papers(papers)
    return {"added": added, "filename": file.filename}


@router.delete("/library/{paper_id}")
async def delete_from_library(paper_id: str):
    """Remove a single paper from the local library."""
    library_store = _main.library_store
    if library_store is None:
        raise HTTPException(503, "Library store not ready")
    deleted = library_store.delete_paper(paper_id)
    if not deleted:
        raise HTTPException(404, "Paper not found")
    return {"deleted": paper_id}
