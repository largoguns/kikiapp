"""Configuración de Kiki App. Todo se lee de variables de entorno."""

from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


APP_NAME = "Kiki App"
APP_VERSION = "1.0.0"

PORT = _env_int("PORT", 8080)
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "kiki.db"))

TIMEZONE = os.getenv("TZ", "Europe/Madrid")
try:
    LOCAL_TZ = ZoneInfo(TIMEZONE)
except (ZoneInfoNotFoundError, ValueError):
    LOCAL_TZ = ZoneInfo("UTC")

# --- Google Sheets ---------------------------------------------------------
GOOGLE_SHEETS_CREDENTIALS_FILE = Path(
    os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", BASE_DIR / "credentials.json")
)
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Kiki")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
GOOGLE_WORKSHEET_NAME = os.getenv("GOOGLE_WORKSHEET_NAME", "Kikis")

SYNC_ENABLED = _env_bool("SYNC_ENABLED", True)
SYNC_ON_STARTUP = _env_bool("SYNC_ON_STARTUP", True)
SYNC_INTERVAL_MINUTES = _env_int("SYNC_INTERVAL_MINUTES", 360)
# Espera antes de empujar a la hoja tras una escritura, para agrupar ráfagas.
SYNC_PUSH_DEBOUNCE_SECONDS = _env_int("SYNC_PUSH_DEBOUNCE_SECONDS", 5)

DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
