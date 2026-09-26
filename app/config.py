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

DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
