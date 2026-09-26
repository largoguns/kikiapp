"""Punto de entrada de Kiki App (FastAPI)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import config, crud, db
from app.routers import events, importer, statistics
from app.services import importer as importer_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("kiki")

STATIC_DIR = config.BASE_DIR / "static"
TEMPLATES_DIR = config.BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    logger.info("Base de datos lista en %s", config.DB_PATH)
    yield


app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description="Registro y análisis de encuentros, desencuentros y ciclo menstrual.",
    lifespan=lifespan,
)

app.include_router(events.router)
app.include_router(statistics.router)
app.include_router(importer.router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _render(request: Request, plantilla: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name=plantilla,
        context={"version": config.APP_VERSION, "app_name": config.APP_NAME},
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard(request: Request) -> HTMLResponse:
    return _render(request, "dashboard.html")


@app.get("/m", response_class=HTMLResponse, include_in_schema=False)
def mobile(request: Request) -> HTMLResponse:
    return _render(request, "mobile.html")


# El Service Worker y el manifest se sirven desde la raíz para que su ámbito
# cubra tanto "/" como "/m".
@app.get("/sw.js", include_in_schema=False)
def service_worker() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest() -> FileResponse:
    return FileResponse(STATIC_DIR / "manifest.webmanifest",
                        media_type="application/manifest+json")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "icons/favicon.svg", media_type="image/svg+xml")


@app.get("/api/health", tags=["sistema"], summary="Estado del servicio")
def health() -> Any:
    return JSONResponse(
        {
            "status": "ok",
            "app": config.APP_NAME,
            "version": config.APP_VERSION,
            "registros": crud.count_events(),
            "timezone": config.TIMEZONE,
            "ultima_importacion": importer_service.ultima_importacion(),
        }
    )
