"""Modelos Pydantic (contratos de la API) y vocabulario del dominio."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TIPO_KIKI = "Kiki"
TIPO_NO_KIKI = "No Kiki"
TIPO_MAREA = "Marea"
TIPOS: tuple[str, ...] = (TIPO_KIKI, TIPO_NO_KIKI, TIPO_MAREA)

MOTIVACIONES: tuple[str, ...] = ("Propia", "Ajena", "Ambos")

# Sugerencias iniciales; la API devuelve además los pretextos ya usados en la BBDD.
PRETEXTOS_SUGERIDOS: tuple[str, ...] = (
    "Desatranque",
    "Cumpleaños",
    "Calentura",
    "Necesidad",
    "Aniversario",
    "Reconciliación",
    "Rutina",
    "Viaje",
    "N/A",
)

TipoEvento = Literal["Kiki", "No Kiki", "Marea"]
Motivacion = Literal["Propia", "Ajena", "Ambos"]


class EventBase(BaseModel):
    fecha: date
    tipo: TipoEvento
    pretexto: Optional[str] = None
    motivacion: Optional[Motivacion] = None
    calidad: int = Field(default=0, ge=0, le=4)
    tiempo: int = Field(default=0, ge=0, le=4)
    observaciones: Optional[str] = None

    @field_validator("pretexto", "observaciones", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("motivacion", mode="before")
    @classmethod
    def _normalize_motivacion(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip().capitalize()
            return value or None
        return value

    @model_validator(mode="after")
    def _only_kiki_is_scored(self) -> "EventBase":
        # Un "No Kiki" o una "Marea" no se puntúan: la especificación fija 0.
        if self.tipo != TIPO_KIKI:
            object.__setattr__(self, "calidad", 0)
            object.__setattr__(self, "tiempo", 0)
        return self


class EventCreate(EventBase):
    pass


class EventUpdate(EventBase):
    pass


class Event(EventBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: str
    updated_at: str


class EventPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[Event]


class Options(BaseModel):
    tipos: list[str]
    motivaciones: list[str]
    pretextos: list[str]
    years: list[int]


class SyncStatus(BaseModel):
    enabled: bool
    configured: bool
    running: bool
    last_sync_at: Optional[str] = None
    last_result: Optional[str] = None
    last_error: Optional[str] = None
    pulled: int = 0
    pushed: int = 0
    sheet: Optional[str] = None
    interval_minutes: int = 0
