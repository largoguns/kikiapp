"""Pasarela con Google Sheets vía `gspread` y una Cuenta de Servicio.

El módulo es tolerante: si `gspread` no está instalado o no hay fichero de
credenciales, la app sigue funcionando en modo local y la sincronización
queda desactivada.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date, timedelta
from typing import Any, Optional

from app import config
from app.schemas import MOTIVACIONES, TIPO_KIKI, TIPO_MAREA, TIPO_NO_KIKI

logger = logging.getLogger(__name__)

HEADERS = [
    "id",
    "fecha",
    "tipo",
    "pretexto",
    "motivacion",
    "calidad",
    "tiempo",
    "observaciones",
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Alias de cabecera aceptados al leer la hoja (sin acentos ni mayúsculas).
HEADER_ALIASES: dict[str, str] = {
    "id": "id",
    "fecha": "fecha",
    "dia": "fecha",
    "date": "fecha",
    "tipo": "tipo",
    "categoria": "tipo",
    "evento": "tipo",
    "pretexto": "pretexto",
    "motivo": "pretexto",
    "excusa": "pretexto",
    "motivacion": "motivacion",
    "iniciativa": "motivacion",
    "quien": "motivacion",
    "calidad": "calidad",
    "nota": "calidad",
    "tiempo": "tiempo",
    "duracion": "tiempo",
    "observaciones": "observaciones",
    "comentarios": "observaciones",
    "notas": "observaciones",
}

TIPO_ALIASES: dict[str, str] = {
    "kiki": TIPO_KIKI,
    "si": TIPO_KIKI,
    "encuentro": TIPO_KIKI,
    "nokiki": TIPO_NO_KIKI,
    "no": TIPO_NO_KIKI,
    "desencuentro": TIPO_NO_KIKI,
    "marea": TIPO_MAREA,
    "regla": TIPO_MAREA,
    "periodo": TIPO_MAREA,
    "menstruacion": TIPO_MAREA,
}

# Origen del contador de fechas de Google Sheets.
EPOCA_SHEETS = date(1899, 12, 30)


class SheetsError(RuntimeError):
    """Cualquier fallo al hablar con Google Sheets."""


def _slug(value: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", value or "")
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", sin_acentos.lower())


def normalize_tipo(value: Any) -> Optional[str]:
    slug = _slug(str(value or ""))
    return TIPO_ALIASES.get(slug)


def normalize_motivacion(value: Any) -> Optional[str]:
    slug = _slug(str(value or ""))
    for motivacion in MOTIVACIONES:
        if _slug(motivacion) == slug:
            return motivacion
    return None


def normalize_fecha(value: Any) -> Optional[str]:
    """Acepta ISO, dd/mm/aaaa, dd-mm-aaaa y el número de serie de Sheets."""
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value.isoformat()

    texto = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
        return texto
    if re.fullmatch(r"\d+", texto):
        return (EPOCA_SHEETS + timedelta(days=int(texto))).isoformat()

    match = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", texto)
    if match:
        dia, mes, anio = (int(part) for part in match.groups())
        if anio < 100:
            anio += 2000
        try:
            return date(anio, mes, dia).isoformat()
        except ValueError:
            return None
    return None


def _score(value: Any) -> int:
    try:
        numero = int(float(str(value).strip().replace(",", ".")))
    except (TypeError, ValueError):
        return 0
    return max(0, min(4, numero))


def row_to_record(raw: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Convierte una fila cruda de la hoja al esquema interno, o None si es basura."""
    normalizado: dict[str, Any] = {}
    for clave, valor in raw.items():
        destino = HEADER_ALIASES.get(_slug(str(clave)))
        if destino and normalizado.get(destino) in (None, ""):
            normalizado[destino] = valor

    fecha = normalize_fecha(normalizado.get("fecha"))
    tipo = normalize_tipo(normalizado.get("tipo"))
    if not fecha or not tipo:
        return None

    def texto(campo: str) -> Optional[str]:
        valor = str(normalizado.get(campo) or "").strip()
        return valor or None

    es_kiki = tipo == TIPO_KIKI
    identificador = str(normalizado.get("id") or "").strip()

    return {
        "id": int(identificador) if identificador.isdigit() else None,
        "fecha": fecha,
        "tipo": tipo,
        "pretexto": texto("pretexto"),
        "motivacion": normalize_motivacion(normalizado.get("motivacion")),
        "calidad": _score(normalizado.get("calidad")) if es_kiki else 0,
        "tiempo": _score(normalizado.get("tiempo")) if es_kiki else 0,
        "observaciones": texto("observaciones"),
    }


def record_to_row(record: dict[str, Any]) -> list[Any]:
    return [
        record.get("id") or "",
        record.get("fecha") or "",
        record.get("tipo") or "",
        record.get("pretexto") or "",
        record.get("motivacion") or "",
        record.get("calidad", 0),
        record.get("tiempo", 0),
        record.get("observaciones") or "",
    ]


def is_configured() -> bool:
    """¿Hay credenciales y librería para hablar con Google Sheets?"""
    if not config.GOOGLE_SHEETS_CREDENTIALS_FILE.is_file():
        return False
    try:
        import gspread  # noqa: F401
    except ImportError:
        return False
    return True


def describe_target() -> str:
    if config.GOOGLE_SHEET_ID:
        return f"id:{config.GOOGLE_SHEET_ID}"
    return config.GOOGLE_SHEET_NAME


class SheetsGateway:
    """Abre la hoja bajo demanda y cachea el handle del worksheet."""

    def __init__(self) -> None:
        self._worksheet = None

    def _open(self):
        if self._worksheet is not None:
            return self._worksheet

        try:
            import gspread
        except ImportError as error:  # pragma: no cover - depende del entorno
            raise SheetsError("gspread no está instalado") from error

        if not config.GOOGLE_SHEETS_CREDENTIALS_FILE.is_file():
            raise SheetsError(
                f"No se encuentra el fichero de credenciales "
                f"{config.GOOGLE_SHEETS_CREDENTIALS_FILE}"
            )

        try:
            cliente = gspread.service_account(
                filename=str(config.GOOGLE_SHEETS_CREDENTIALS_FILE), scopes=SCOPES
            )
            libro = (
                cliente.open_by_key(config.GOOGLE_SHEET_ID)
                if config.GOOGLE_SHEET_ID
                else cliente.open(config.GOOGLE_SHEET_NAME)
            )
            try:
                worksheet = libro.worksheet(config.GOOGLE_WORKSHEET_NAME)
            except Exception:
                worksheet = libro.sheet1
        except SheetsError:
            raise
        except Exception as error:
            raise SheetsError(f"No se pudo abrir la hoja: {error}") from error

        self._worksheet = worksheet
        return worksheet

    def pull(self) -> list[dict[str, Any]]:
        """Descarga la hoja completa ya normalizada al esquema interno."""
        worksheet = self._open()
        try:
            filas = worksheet.get_all_values()
        except Exception as error:
            raise SheetsError(f"Error leyendo la hoja: {error}") from error

        if not filas:
            return []

        cabecera = filas[0]
        registros = []
        for fila in filas[1:]:
            if not any(str(celda).strip() for celda in fila):
                continue
            crudo = dict(zip(cabecera, fila))
            registro = row_to_record(crudo)
            if registro:
                registros.append(registro)
        return registros

    def push(self, records: list[dict[str, Any]]) -> int:
        """Reescribe la hoja con el estado completo de la BBDD local.

        El dataset es pequeño, así que una reescritura íntegra es más simple y
        fiable que llevar un diario de cambios por fila.
        """
        worksheet = self._open()
        valores = [HEADERS] + [record_to_row(record) for record in records]
        try:
            worksheet.clear()
            worksheet.update(
                values=valores, range_name="A1", value_input_option="USER_ENTERED"
            )
        except Exception as error:
            raise SheetsError(f"Error escribiendo en la hoja: {error}") from error
        return len(records)

    def reset(self) -> None:
        self._worksheet = None


gateway = SheetsGateway()
