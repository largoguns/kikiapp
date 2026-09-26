"""Métricas derivadas: sequías y ciclo menstrual."""

from __future__ import annotations

from datetime import date

from app import stats


def test_mayor_sequia_incluye_la_racha_en_curso():
    kikis = [date(2026, 1, 1), date(2026, 1, 11), date(2026, 2, 1)]
    hoy = date(2026, 2, 5)
    resultado = stats._longest_dry_spell(kikis, hoy)
    assert resultado["dias"] == 21  # del 11/01 al 01/02
    assert resultado["desde"] == "2026-01-11"

    # Si la sequía actual supera al récord, gana ella.
    assert stats._longest_dry_spell(kikis, date(2026, 3, 15))["dias"] == 42


def test_ciclo_agrupa_dias_consecutivos_en_periodos():
    dias = [
        date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4),
        date(2026, 1, 29), date(2026, 1, 30), date(2026, 1, 31),
    ]
    ciclo = stats.cycle_stats(dias, date(2026, 2, 5))
    assert ciclo["periodos_registrados"] == 2
    assert ciclo["duracion_media_dias"] == 3.5
    assert ciclo["ciclo_medio_dias"] == 28
    assert ciclo["ultimo_periodo_inicio"] == "2026-01-29"
    assert ciclo["dia_del_ciclo"] == 8
    assert ciclo["proxima_prevista"] == "2026-02-26"


def test_ciclo_tolera_un_dia_sin_registrar():
    # Hueco de 2 días: sigue siendo el mismo período.
    dias = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 4)]
    assert stats.cycle_stats(dias, date(2026, 1, 10))["periodos_registrados"] == 1


def test_ciclo_sin_datos_no_revienta():
    ciclo = stats.cycle_stats([], date(2026, 1, 1))
    assert ciclo["periodos_registrados"] == 0
    assert ciclo["proxima_prevista"] is None
