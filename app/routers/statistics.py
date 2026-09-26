"""Estadísticas, series temporales y datos de calendario."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Query

from app import stats
from app.routers.common import Filters

router = APIRouter(prefix="/api/stats", tags=["estadísticas"])


@router.get("/summary", summary="KPIs principales")
def get_summary(filters: Filters) -> Any:
    return stats.summary(filters)


@router.get("/monthly", summary="Serie mensual de un año")
def get_monthly(
    filters: Filters,
    year: Annotated[Optional[int], Query(ge=1970, le=2200)] = None,
) -> Any:
    objetivo = year or filters.year or stats.today().year
    return {"year": objetivo, "meses": stats.monthly(objetivo, filters)}


@router.get("/yearly", summary="Serie anual histórica")
def get_yearly(filters: Filters) -> Any:
    return {"anios": stats.yearly(filters)}


@router.get("/breakdown", summary="Reparto por motivación y pretexto")
def get_breakdown(filters: Filters) -> Any:
    return stats.breakdown(filters)


@router.get("/calendar", summary="Eventos agrupados por día")
def get_calendar(
    filters: Filters,
    year: Annotated[Optional[int], Query(ge=1970, le=2200)] = None,
    month: Annotated[Optional[int], Query(ge=1, le=12)] = None,
) -> Any:
    objetivo = year or filters.year or stats.today().year
    return stats.calendar(objetivo, month, filters)
