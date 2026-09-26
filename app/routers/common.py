"""Dependencias compartidas por los routers."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Query

from app.crud import EventFilters


def get_filters(
    year: Annotated[Optional[int], Query(ge=1970, le=2200)] = None,
    desde: Annotated[Optional[str], Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
    hasta: Annotated[Optional[str], Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
    tipo: Annotated[Optional[list[str]], Query()] = None,
    motivacion: Annotated[Optional[list[str]], Query()] = None,
    pretexto: Annotated[Optional[list[str]], Query()] = None,
    tag: Annotated[Optional[list[str]], Query()] = None,
    min_calidad: Annotated[Optional[int], Query(ge=0, le=4)] = None,
    min_tiempo: Annotated[Optional[int], Query(ge=0, le=4)] = None,
    q: Annotated[Optional[str], Query(max_length=120)] = None,
) -> EventFilters:
    return EventFilters(
        year=year,
        desde=desde,
        hasta=hasta,
        tipo=tipo,
        motivacion=motivacion,
        pretexto=pretexto,
        tag=tag,
        min_calidad=min_calidad,
        min_tiempo=min_tiempo,
        q=q,
    )


Filters = Annotated[EventFilters, Depends(get_filters)]
