"""Importación única del histórico desde un fichero de hoja de cálculo."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.services import importer

router = APIRouter(prefix="/api/import", tags=["importación"])

Modo = Literal["combinar", "reemplazar"]


@router.get("", summary="Última importación realizada")
def estado() -> Any:
    return {"ultima_importacion": importer.ultima_importacion()}


@router.post("", summary="Importar un .xlsx o .csv")
async def importar(
    archivo: Annotated[UploadFile, File(description="Fichero .xlsx o .csv")],
    modo: Annotated[Modo, Form()] = "combinar",
    simular: Annotated[bool, Form()] = False,
    hoja: Annotated[Optional[str], Form()] = None,
) -> Any:
    contenido = await archivo.read()
    try:
        return await run_in_threadpool(
            importer.importar,
            contenido,
            archivo.filename or "sin-nombre",
            modo,
            simular,
            hoja or None,
        )
    except importer.ImportError_ as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
