"""Capa de acceso a SQLite: conexión, esquema y tabla de metadatos."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional

from app import config
from app.schemas import TIPOS_CON_CONTEXTO, TIPOS_CON_TAGS, TIPOS_PUNTUADOS

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha         TEXT    NOT NULL,
    tipo          TEXT    NOT NULL,
    pretexto      TEXT,
    motivacion    TEXT,
    calidad       INTEGER NOT NULL DEFAULT 0,
    tiempo        INTEGER NOT NULL DEFAULT 0,
    observaciones TEXT,
    tags          TEXT    NOT NULL DEFAULT '[]',
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_fecha ON events (fecha);
CREATE INDEX IF NOT EXISTS idx_events_tipo  ON events (tipo);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Conexión por operación, con commit/rollback automático."""
    conn = sqlite3.connect(config.DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
    migrar_columnas()
    normalizar_por_tipo()


def migrar_columnas() -> None:
    """Añade las columnas que falten en bases creadas por versiones previas."""
    nuevas = {"tags": "TEXT NOT NULL DEFAULT '[]'"}
    with connect() as conn:
        existentes = {fila[1] for fila in conn.execute("PRAGMA table_info(events)")}
        for nombre, definicion in nuevas.items():
            if nombre not in existentes:
                conn.execute(f"ALTER TABLE events ADD COLUMN {nombre} {definicion}")
                logger.info("Columna «%s» añadida a events", nombre)


def normalizar_por_tipo() -> int:
    """Borra de la tabla los campos que no corresponden al tipo del registro.

    El modelo ya los vacía al escribir, pero las reglas de qué campos lleva
    cada categoría han cambiado con el tiempo. Esto pone al día las filas
    antiguas al arrancar, para que lo guardado y lo que devuelve la API digan
    lo mismo. Devuelve cuántas filas ha corregido; es idempotente, así que en
    una base ya limpia no toca nada.
    """
    puntuados = ", ".join("?" for _ in TIPOS_PUNTUADOS)
    con_contexto = ", ".join("?" for _ in TIPOS_CON_CONTEXTO)
    con_tags = ", ".join("?" for _ in TIPOS_CON_TAGS)

    # Una sola sentencia: así el recuento son filas, no correcciones sueltas.
    sql = f"""
        UPDATE events
           SET calidad    = CASE WHEN tipo IN ({puntuados}) THEN calidad ELSE 0 END,
               tiempo     = CASE WHEN tipo IN ({puntuados}) THEN tiempo  ELSE 0 END,
               pretexto   = CASE WHEN tipo IN ({con_contexto}) THEN pretexto   ELSE NULL END,
               motivacion = CASE WHEN tipo IN ({con_contexto}) THEN motivacion ELSE NULL END,
               tags       = CASE WHEN tipo IN ({con_tags}) THEN tags ELSE '[]' END
         WHERE (tipo NOT IN ({puntuados}) AND (calidad <> 0 OR tiempo <> 0))
            OR (tipo NOT IN ({con_contexto})
                AND (pretexto IS NOT NULL OR motivacion IS NOT NULL))
            OR (tipo NOT IN ({con_tags})
                AND tags IS NOT NULL AND tags <> '[]')
    """
    parametros = (
        *TIPOS_PUNTUADOS, *TIPOS_PUNTUADOS, *TIPOS_CON_CONTEXTO,
        *TIPOS_CON_CONTEXTO, *TIPOS_CON_TAGS,
        *TIPOS_PUNTUADOS, *TIPOS_CON_CONTEXTO, *TIPOS_CON_TAGS,
    )

    with connect() as conn:
        corregidas = conn.execute(sql, parametros).rowcount

    if corregidas:
        logger.info("Normalizadas %d filas con campos ajenos a su tipo", corregidas)
    return corregidas


def get_meta(key: str, default: Optional[str] = None) -> Optional[str]:
    with connect() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(key: str, value: Optional[str]) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
