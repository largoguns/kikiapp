"""Control de la sincronización con Google Sheets."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.schemas import SyncStatus
from app.services.sync import Direction, manager

router = APIRouter(prefix="/api/sync", tags=["sincronización"])


@router.get("", response_model=SyncStatus, summary="Estado de la sincronización")
def get_status() -> Any:
    return manager.status()


@router.post("", summary="Forzar sincronización")
async def force_sync(
    direction: Annotated[Direction, Query(description="both | pull | push")] = "both",
) -> Any:
    return await manager.sync(direction)
