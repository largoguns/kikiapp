"""Orquestación de la sincronización bidireccional con Google Sheets.

Flujo de una sincronización completa:
  1. `pull`  : lee la hoja y fusiona los cambios en SQLite.
  2. `push`  : reescribe la hoja con el estado completo local.

Las filas de la hoja con `id` conocido mandan sobre la copia local (así las
ediciones hechas a mano en Drive se respetan); las filas sin `id` se emparejan
por (fecha, tipo) y, si no existen, se insertan y reciben un `id` en el push.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from app import config, crud, db
from app.services import sheets

logger = logging.getLogger(__name__)

Direction = Literal["both", "pull", "push"]

META_LAST_SYNC = "sync.last_sync_at"


class SyncManager:
    """Punto único de entrada a la sincronización. Serializa las operaciones."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._loop_task: Optional[asyncio.Task] = None
        self._push_task: Optional[asyncio.Task] = None
        self.running = False
        self.last_result: Optional[str] = None
        self.last_error: Optional[str] = None
        self.last_pulled = 0
        self.last_pushed = 0

    # --- ciclo de vida ----------------------------------------------------
    async def start(self) -> None:
        if not config.SYNC_ENABLED:
            logger.info("Sincronización con Google Sheets desactivada (SYNC_ENABLED)")
            return
        if not sheets.is_configured():
            logger.warning(
                "Sin credenciales en %s: la app funciona en local sin sincronizar",
                config.GOOGLE_SHEETS_CREDENTIALS_FILE,
            )
            return
        self._loop_task = asyncio.create_task(self._periodic_loop())

    async def stop(self) -> None:
        for task in (self._loop_task, self._push_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: B014
                    pass
        self._loop_task = self._push_task = None

    async def _periodic_loop(self) -> None:
        if config.SYNC_ON_STARTUP:
            await self.sync("both")
        intervalo = max(config.SYNC_INTERVAL_MINUTES, 1) * 60
        while True:
            await asyncio.sleep(intervalo)
            await self.sync("both")

    # --- operaciones ------------------------------------------------------
    async def sync(self, direction: Direction = "both") -> dict[str, Any]:
        if not config.SYNC_ENABLED:
            return self._fail("La sincronización está desactivada")
        if not sheets.is_configured():
            return self._fail("Google Sheets no está configurado (faltan credenciales)")

        async with self._lock:
            self.running = True
            try:
                pulled = pushed = 0
                if direction in ("both", "pull"):
                    pulled = await asyncio.to_thread(self._pull_blocking)
                if direction in ("both", "push"):
                    pushed = await asyncio.to_thread(self._push_blocking)
            except sheets.SheetsError as error:
                logger.error("Fallo de sincronización: %s", error)
                sheets.gateway.reset()
                return self._fail(str(error))
            except Exception as error:  # pragma: no cover - red/API
                logger.exception("Fallo inesperado de sincronización")
                sheets.gateway.reset()
                return self._fail(str(error))
            finally:
                self.running = False

            self.last_pulled, self.last_pushed = pulled, pushed
            self.last_error = None
            self.last_result = f"{pulled} importados / {pushed} exportados"
            db.set_meta(META_LAST_SYNC, datetime.now(timezone.utc).isoformat())
            logger.info("Sincronización OK: %s", self.last_result)
            return self.status() | {"ok": True}

    def _fail(self, mensaje: str) -> dict[str, Any]:
        self.running = False
        self.last_error = mensaje
        self.last_result = None
        return self.status() | {"ok": False}

    def _pull_blocking(self) -> int:
        remotos = sheets.gateway.pull()
        pendientes: list[dict[str, Any]] = []
        for registro in remotos:
            if registro["id"]:
                pendientes.append(registro)
                continue
            # Sin id: sólo se inserta si no hay ya un evento equivalente.
            if not crud.find_by_fingerprint(registro["fecha"], registro["tipo"]):
                pendientes.append(registro)
        if not pendientes:
            return 0
        insertados, actualizados = crud.upsert_many(pendientes)
        return insertados + actualizados

    def _push_blocking(self) -> int:
        registros, _ = crud.list_events(sort="fecha", order="asc")
        return sheets.gateway.push(registros)

    def schedule_push(self) -> None:
        """Exporta en segundo plano tras una escritura, agrupando ráfagas."""
        if not (config.SYNC_ENABLED and sheets.is_configured()):
            return
        if self._push_task and not self._push_task.done():
            return
        self._push_task = asyncio.create_task(self._debounced_push())

    async def _debounced_push(self) -> None:
        try:
            await asyncio.sleep(max(config.SYNC_PUSH_DEBOUNCE_SECONDS, 0))
            await self.sync("push")
        except asyncio.CancelledError:  # pragma: no cover
            raise
        except Exception:  # pragma: no cover
            logger.exception("Fallo en la exportación diferida")

    # --- estado -----------------------------------------------------------
    def status(self) -> dict[str, Any]:
        return {
            "enabled": config.SYNC_ENABLED,
            "configured": sheets.is_configured(),
            "running": self.running,
            "last_sync_at": db.get_meta(META_LAST_SYNC),
            "last_result": self.last_result,
            "last_error": self.last_error,
            "pulled": self.last_pulled,
            "pushed": self.last_pushed,
            "sheet": sheets.describe_target(),
            "interval_minutes": config.SYNC_INTERVAL_MINUTES,
        }


manager = SyncManager()
