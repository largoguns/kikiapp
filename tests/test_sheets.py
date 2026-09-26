"""Normalización de las filas que llegan de Google Sheets."""

from __future__ import annotations

import pytest

from app.services import sheets


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("2026-03-10", "2026-03-10"),
        ("10/03/2026", "2026-03-10"),
        ("10-3-26", "2026-03-10"),
        ("46091", "2026-03-10"),   # número de serie de Sheets
        ("", None),
        ("no es fecha", None),
        ("32/13/2026", None),
    ],
)
def test_normalize_fecha(entrada, esperado):
    assert sheets.normalize_fecha(entrada) == esperado


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("Kiki", "Kiki"), ("kiki", "Kiki"), ("Encuentro", "Kiki"),
        ("No Kiki", "No Kiki"), ("no-kiki", "No Kiki"), ("NOKIKI", "No Kiki"),
        ("Marea", "Marea"), ("menstruación", "Marea"), ("Regla", "Marea"),
        ("otra cosa", None),
    ],
)
def test_normalize_tipo(entrada, esperado):
    assert sheets.normalize_tipo(entrada) == esperado


def test_row_to_record_acepta_alias_de_cabecera():
    crudo = {
        "Id": "12",
        "Día": "10/03/2026",
        "Categoría": "kiki",
        "Motivo": " Calentura ",
        "Iniciativa": "AMBOS",
        "Nota": "3",
        "Duración": "2",
        "Comentarios": " sin más ",
    }
    registro = sheets.row_to_record(crudo)
    assert registro == {
        "id": 12,
        "fecha": "2026-03-10",
        "tipo": "Kiki",
        "pretexto": "Calentura",
        "motivacion": "Ambos",
        "calidad": 3,
        "tiempo": 2,
        "observaciones": "sin más",
    }


def test_row_to_record_descarta_filas_sin_fecha_o_tipo():
    assert sheets.row_to_record({"fecha": "", "tipo": "Kiki"}) is None
    assert sheets.row_to_record({"fecha": "2026-03-10", "tipo": ""}) is None


def test_row_to_record_fuerza_cero_fuera_de_los_kiki():
    registro = sheets.row_to_record(
        {"fecha": "2026-03-10", "tipo": "Marea", "calidad": "4", "tiempo": "4"}
    )
    assert (registro["calidad"], registro["tiempo"]) == (0, 0)


def test_valoraciones_se_acotan_al_rango():
    registro = sheets.row_to_record(
        {"fecha": "2026-03-10", "tipo": "Kiki", "calidad": "9", "tiempo": "-2"}
    )
    assert (registro["calidad"], registro["tiempo"]) == (4, 0)


def test_record_to_row_respeta_el_orden_de_cabecera():
    fila = sheets.record_to_row(
        {"id": 3, "fecha": "2026-03-10", "tipo": "Kiki", "pretexto": None,
         "motivacion": "Propia", "calidad": 2, "tiempo": 1, "observaciones": None}
    )
    assert fila == [3, "2026-03-10", "Kiki", "", "Propia", 2, 1, ""]
    assert len(fila) == len(sheets.HEADERS)
