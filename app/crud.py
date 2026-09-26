"""Operaciones de lectura/escritura sobre la tabla `events`."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

from app import db
from app.schemas import EventCreate, EventRange, EventUpdate

SORTABLE = {"id", "fecha", "tipo", "pretexto", "motivacion", "calidad", "tiempo"}

COLUMNS = (
    "id",
    "fecha",
    "tipo",
    "pretexto",
    "motivacion",
    "calidad",
    "tiempo",
    "observaciones",
    "tags",
    "created_at",
    "updated_at",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    datos = {key: row[key] for key in row.keys()}
    if "tags" in datos:
        datos["tags"] = _leer_tags(datos["tags"])
    return datos


def _leer_tags(valor: Any) -> list[str]:
    """La columna guarda un array JSON; una base antigua puede traer NULL."""
    if isinstance(valor, list):
        return valor
    if not valor:
        return []
    try:
        etiquetas = json.loads(valor)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in etiquetas] if isinstance(etiquetas, list) else []


def _escribir_tags(etiquetas: Any) -> str:
    return json.dumps(list(etiquetas or []), ensure_ascii=False)


class EventFilters:
    """Filtros aplicables al listado y a las estadísticas."""

    def __init__(
        self,
        year: Optional[int] = None,
        desde: Optional[str] = None,
        hasta: Optional[str] = None,
        tipo: Optional[Sequence[str]] = None,
        motivacion: Optional[Sequence[str]] = None,
        pretexto: Optional[Sequence[str]] = None,
        tag: Optional[Sequence[str]] = None,
        min_calidad: Optional[int] = None,
        min_tiempo: Optional[int] = None,
        q: Optional[str] = None,
    ) -> None:
        self.year = year
        self.desde = desde
        self.hasta = hasta
        self.tipo = list(tipo) if tipo else []
        self.motivacion = list(motivacion) if motivacion else []
        self.pretexto = list(pretexto) if pretexto else []
        self.tag = list(tag) if tag else []
        self.min_calidad = min_calidad
        self.min_tiempo = min_tiempo
        self.q = (q or "").strip()

    def where(self) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if self.year:
            clauses.append("substr(fecha, 1, 4) = ?")
            params.append(f"{self.year:04d}")
        if self.desde:
            clauses.append("fecha >= ?")
            params.append(self.desde)
        if self.hasta:
            clauses.append("fecha <= ?")
            params.append(self.hasta)
        for column, values in (
            ("tipo", self.tipo),
            ("motivacion", self.motivacion),
            ("pretexto", self.pretexto),
        ):
            if values:
                placeholders = ", ".join("?" for _ in values)
                clauses.append(f"{column} IN ({placeholders})")
                params.extend(values)
        if self.tag:
            # Basta con que el registro lleve alguna de las etiquetas pedidas.
            placeholders = ", ".join("?" for _ in self.tag)
            clauses.append(
                f"EXISTS (SELECT 1 FROM json_each(events.tags) "
                f"WHERE json_each.value IN ({placeholders}))"
            )
            params.extend(self.tag)
        # Las puntuaciones sólo existen en los "Kiki"; filtrar por ellas
        # no debe arrastrar los ceros forzados de "No Kiki"/"Marea".
        if self.min_calidad is not None:
            clauses.append("calidad >= ?")
            params.append(self.min_calidad)
        if self.min_tiempo is not None:
            clauses.append("tiempo >= ?")
            params.append(self.min_tiempo)
        if self.q:
            clauses.append(
                "(IFNULL(observaciones, '') LIKE ? OR IFNULL(pretexto, '') LIKE ? "
                "OR IFNULL(motivacion, '') LIKE ? OR tipo LIKE ? OR fecha LIKE ?)"
            )
            params.extend([f"%{self.q}%"] * 5)

        sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return sql, params


def list_events(
    filters: Optional[EventFilters] = None,
    sort: str = "fecha",
    order: str = "desc",
    limit: Optional[int] = None,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    filters = filters or EventFilters()
    where, params = filters.where()

    sort = sort if sort in SORTABLE else "fecha"
    direction = "ASC" if order.lower() == "asc" else "DESC"

    with db.connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n FROM events{where}", params).fetchone()["n"]
        sql = f"SELECT * FROM events{where} ORDER BY {sort} {direction}, id {direction}"
        query_params = list(params)
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            query_params.extend([limit, max(offset, 0)])
        rows = conn.execute(sql, query_params).fetchall()

    return [row_to_dict(row) for row in rows], total


def get_event(event_id: int) -> Optional[dict[str, Any]]:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return row_to_dict(row) if row else None


def create_event(payload: EventCreate) -> dict[str, Any]:
    now = _now()
    with db.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO events
                (fecha, tipo, pretexto, motivacion, calidad, tiempo, observaciones,
                 tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.fecha.isoformat(),
                payload.tipo,
                payload.pretexto,
                payload.motivacion,
                payload.calidad,
                payload.tiempo,
                payload.observaciones,
                _escribir_tags(payload.tags),
                now,
                now,
            ),
        )
        event_id = int(cursor.lastrowid)
    created = get_event(event_id)
    assert created is not None
    return created


def create_range(payload: EventRange) -> tuple[list[dict[str, Any]], int]:
    """Crea un registro por cada día del rango, ambos extremos incluidos.

    Los días que ya tienen un evento de ese mismo tipo se omiten, para que
    ampliar un período registrado a medias no duplique los días previos.
    Devuelve (creados, omitidos).
    """
    creados: list[dict[str, Any]] = []
    omitidos = 0
    dia = payload.fecha
    while dia <= payload.hasta:
        if _existe_ese_dia(dia.isoformat(), payload.tipo):
            omitidos += 1
        else:
            creados.append(create_event(EventCreate(**{**payload.model_dump(
                exclude={"hasta"}), "fecha": dia})))
        dia += timedelta(days=1)
    return creados, omitidos


def _existe_ese_dia(fecha: str, tipo: str) -> bool:
    with db.connect() as conn:
        fila = conn.execute(
            "SELECT 1 FROM events WHERE fecha = ? AND tipo = ? LIMIT 1", (fecha, tipo)
        ).fetchone()
    return fila is not None


def update_event(event_id: int, payload: EventUpdate) -> Optional[dict[str, Any]]:
    with db.connect() as conn:
        cursor = conn.execute(
            """
            UPDATE events
               SET fecha = ?, tipo = ?, pretexto = ?, motivacion = ?, calidad = ?,
                   tiempo = ?, observaciones = ?, tags = ?, updated_at = ?
             WHERE id = ?
            """,
            (
                payload.fecha.isoformat(),
                payload.tipo,
                payload.pretexto,
                payload.motivacion,
                payload.calidad,
                payload.tiempo,
                payload.observaciones,
                _escribir_tags(payload.tags),
                _now(),
                event_id,
            ),
        )
        if cursor.rowcount == 0:
            return None
    return get_event(event_id)


def delete_event(event_id: int) -> bool:
    with db.connect() as conn:
        cursor = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
        return cursor.rowcount > 0


def count_events() -> int:
    with db.connect() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]


def distinct_pretextos() -> list[str]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT pretexto FROM events "
            "WHERE pretexto IS NOT NULL AND pretexto <> '' ORDER BY pretexto COLLATE NOCASE"
        ).fetchall()
    return [row["pretexto"] for row in rows]


def distinct_tags() -> list[str]:
    """Etiquetas ya usadas, de la más frecuente a la menos."""
    with db.connect() as conn:
        filas = conn.execute(
            "SELECT json_each.value AS tag, COUNT(*) AS n "
            "FROM events, json_each(events.tags) "
            "GROUP BY tag ORDER BY n DESC, tag COLLATE NOCASE"
        ).fetchall()
    return [fila["tag"] for fila in filas]


def distinct_years() -> list[int]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT CAST(substr(fecha, 1, 4) AS INTEGER) AS y "
            "FROM events ORDER BY y DESC"
        ).fetchall()
    return [row["y"] for row in rows if row["y"]]


def upsert_many(records: list[dict[str, Any]]) -> tuple[int, int]:
    """Inserta o actualiza registros que vienen de Google Sheets.

    Los registros con `id` conocido se actualizan; el resto se insertan
    respetando el `id` remoto si viene informado. Devuelve (insertados,
    actualizados).
    """
    inserted = updated = 0
    now = _now()
    with db.connect() as conn:
        for record in records:
            event_id = record.get("id")
            existing = None
            if event_id:
                existing = conn.execute(
                    "SELECT id FROM events WHERE id = ?", (event_id,)
                ).fetchone()
            values = (
                record["fecha"],
                record["tipo"],
                record.get("pretexto"),
                record.get("motivacion"),
                int(record.get("calidad") or 0),
                int(record.get("tiempo") or 0),
                record.get("observaciones"),
                _escribir_tags(record.get("tags")),
            )
            if existing:
                conn.execute(
                    """
                    UPDATE events
                       SET fecha = ?, tipo = ?, pretexto = ?, motivacion = ?,
                           calidad = ?, tiempo = ?, observaciones = ?, tags = ?,
                           updated_at = ?
                     WHERE id = ?
                    """,
                    (*values, now, event_id),
                )
                updated += 1
            elif event_id:
                conn.execute(
                    """
                    INSERT INTO events
                        (id, fecha, tipo, pretexto, motivacion, calidad, tiempo,
                         observaciones, tags, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (event_id, *values, now, now),
                )
                inserted += 1
            else:
                conn.execute(
                    """
                    INSERT INTO events
                        (fecha, tipo, pretexto, motivacion, calidad, tiempo,
                         observaciones, tags, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*values, now, now),
                )
                inserted += 1
    return inserted, updated


def find_by_fingerprint(fecha: str, tipo: str) -> Optional[dict[str, Any]]:
    """Empareja filas de la hoja que aún no tienen `id` asignado."""
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE fecha = ? AND tipo = ? ORDER BY id LIMIT 1",
            (fecha, tipo),
        ).fetchone()
    return row_to_dict(row) if row else None
