"""Modelos Pydantic (contratos de la API) y vocabulario del dominio."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TIPO_KIKI = "Kiki"
TIPO_NO_KIKI = "No Kiki"
TIPO_GAYOLA = "Gayola"
TIPO_MAREA = "Marea"
TIPOS: tuple[str, ...] = (TIPO_KIKI, TIPO_NO_KIKI, TIPO_GAYOLA, TIPO_MAREA)

# Sólo el Kiki se valora: el resto de categorías no llevan calidad ni tiempo.
TIPOS_PUNTUADOS: tuple[str, ...] = (TIPO_KIKI,)

# Categorías que cuentan para el porcentaje de acierto.
TIPOS_INTENTO: tuple[str, ...] = (TIPO_KIKI, TIPO_NO_KIKI)

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

# Tope de seguridad para el alta por rango: un ciclo largo cabe de sobra.
MAX_DIAS_RANGO = 90

TipoEvento = Literal["Kiki", "No Kiki", "Gayola", "Marea"]
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
        # Sólo el Kiki se valora; las demás categorías quedan a 0.
        if self.tipo not in TIPOS_PUNTUADOS:
            object.__setattr__(self, "calidad", 0)
            object.__setattr__(self, "tiempo", 0)
        return self


class EventCreate(EventBase):
    pass


class EventUpdate(EventBase):
    pass


class EventRange(EventBase):
    """Alta de varios días de una tirada, pensada para el ciclo menstrual."""

    hasta: date

    @model_validator(mode="after")
    def _rango_coherente(self) -> "EventRange":
        if self.hasta < self.fecha:
            raise ValueError("La fecha final no puede ser anterior a la inicial")
        if (self.hasta - self.fecha).days + 1 > MAX_DIAS_RANGO:
            raise ValueError(
                f"El rango no puede superar {MAX_DIAS_RANGO} días"
            )
        return self


class RangeResult(BaseModel):
    creados: int
    omitidos: int
    fechas: list[str]


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

