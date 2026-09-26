"""CRUD de registros (`Kikis`)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.concurrency import run_in_threadpool

from app import crud
from app.routers.common import Filters
from app.schemas import EventCreate, EventPage, EventRange, EventUpdate
from app.schemas import Options, RangeResult
from app.schemas import MOTIVACIONES, PRETEXTOS_SUGERIDOS, TIPOS

router = APIRouter(prefix="/api", tags=["registros"])


@router.get("/events", response_model=EventPage, summary="Listar registros")
def list_events(
    filters: Filters,
    sort: Annotated[str, Query()] = "fecha",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    limit: Annotated[int, Query(ge=1, le=2000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    items, total = crud.list_events(filters, sort=sort, order=order, limit=limit, offset=offset)
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/events/{event_id}", summary="Obtener un registro")
def get_event(event_id: int) -> Any:
    evento = crud.get_event(event_id)
    if not evento:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registro no encontrado")
    return evento


@router.post("/events", status_code=status.HTTP_201_CREATED, summary="Crear registro")
async def create_event(payload: EventCreate) -> Any:
    evento = await run_in_threadpool(crud.create_event, payload)
    return evento


@router.post("/events/rango", response_model=RangeResult,
             status_code=status.HTTP_201_CREATED,
             summary="Crear un registro por cada día de un rango")
async def create_range(payload: EventRange) -> Any:
    """Alta en bloque, pensada para meter un ciclo menstrual de una tirada."""
    creados, omitidos = await run_in_threadpool(crud.create_range, payload)
    return {
        "creados": len(creados),
        "omitidos": omitidos,
        "fechas": [evento["fecha"] for evento in creados],
    }


@router.put("/events/{event_id}", summary="Actualizar registro")
async def update_event(event_id: int, payload: EventUpdate) -> Any:
    evento = await run_in_threadpool(crud.update_event, event_id, payload)
    if not evento:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registro no encontrado")
    return evento


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Eliminar registro")
async def delete_event(event_id: int) -> Response:
    if not await run_in_threadpool(crud.delete_event, event_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registro no encontrado")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/options", response_model=Options, summary="Vocabulario disponible")
def get_options() -> Any:
    usados = crud.distinct_pretextos()
    pretextos = sorted({*PRETEXTOS_SUGERIDOS, *usados}, key=str.casefold)
    return {
        "tipos": list(TIPOS),
        "motivaciones": list(MOTIVACIONES),
        "pretextos": pretextos,
        "years": crud.distinct_years(),
    }
