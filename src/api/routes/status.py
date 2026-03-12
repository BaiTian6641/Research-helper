"""GET /api/v1/status — system health & model info."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from src.api import schemas
import src.api.main as _main

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/status", response_model=schemas.StatusResponse)
async def status():
    """Return system status: LLM availability, model info, paper counts, hardware."""
    llm_ok = False
    model_name: str | None = None
    models_available: list[str] = []

    llm_client = _main.llm_client
    store = _main.store
    library_store = _main.library_store
    hardware_info = _main.hardware_info

    if llm_client is not None:
        try:
            llm_ok = await llm_client.health_check()
            if llm_ok:
                models_available = await llm_client.list_models()
                model_name = llm_client.model
        except Exception:
            logger.warning("LLM health-check failed", exc_info=True)

    paper_count = 0
    library_count = 0
    if store is not None:
        paper_count = store.get_paper_count()
    if library_store is not None:
        library_count = library_store.get_paper_count()

    hw_response = None
    if hardware_info is not None:
        hw_response = schemas.HardwareResponse(
            ram_gb=round(hardware_info.ram_gb, 1),
            gpus=[schemas.HardwareGPU(**g) for g in hardware_info.gpus],
            os_name=hardware_info.os_name,
            llm_capable=hardware_info.llm_capable,
            reason=hardware_info.reason,
        )

    return schemas.StatusResponse(
        llm_available=llm_ok,
        model_name=model_name,
        models_available=models_available,
        paper_count=paper_count,
        library_count=library_count,
        hardware=hw_response,
    )
