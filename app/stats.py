"""Cálculo de KPIs, series temporales y métricas de ciclo menstrual.

El volumen de datos es pequeño (unos cientos de filas al año), así que se
cargan en memoria y se agregan en Python: más legible que hacerlo en SQL y
sin coste apreciable.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any, Optional

from app import config, crud
from app.crud import EventFilters
from app.schemas import TIPO_GAYOLA, TIPO_KIKI, TIPO_MAREA, TIPO_NO_KIKI
from app.schemas import TIPOS, TIPOS_CON_CONTEXTO, TIPOS_INTENTO

MESES = (
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
)
DIAS_SEMANA = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")

# Nombre de cada tipo como clave en los JSON de salida.
CLAVE_TIPO: dict[str, str] = {
    TIPO_KIKI: "kiki",
    TIPO_NO_KIKI: "no_kiki",
    TIPO_GAYOLA: "gayola",
    TIPO_MAREA: "marea",
}


def _contador_vacio() -> dict[str, int]:
    return {clave: 0 for clave in CLAVE_TIPO.values()}


# Tolerancia (en días) para considerar que dos registros de "Marea" pertenecen
# al mismo período aunque falte algún día por registrar.
GAP_MISMO_PERIODO = 2
CICLO_MIN_DIAS = 15
CICLO_MAX_DIAS = 60


def today() -> date:
    return datetime.now(config.LOCAL_TZ).date()


def _parse(value: str) -> Optional[date]:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _avg(values: list[float]) -> Optional[float]:
    return round(mean(values), 2) if values else None


def _fetch(filters: Optional[EventFilters]) -> list[dict[str, Any]]:
    rows, _ = crud.list_events(filters=filters, sort="fecha", order="asc")
    return rows


def _dates_of(rows: list[dict[str, Any]], tipo: str) -> list[date]:
    fechas = [_parse(row["fecha"]) for row in rows if row["tipo"] == tipo]
    return sorted(fecha for fecha in fechas if fecha is not None)


def summary(filters: Optional[EventFilters] = None) -> dict[str, Any]:
    rows = _fetch(filters)
    hoy = today()

    kikis = [row for row in rows if row["tipo"] == TIPO_KIKI]
    calidades = [row["calidad"] for row in kikis]
    tiempos = [row["tiempo"] for row in kikis]

    totales = _contador_vacio()
    for row in rows:
        clave = CLAVE_TIPO.get(row["tipo"])
        if clave:
            totales[clave] += 1

    # El acierto compara sólo Kiki contra No Kiki: Gayola y Marea son
    # categorías aparte y no entran en la cuenta.
    intentos = sum(1 for row in rows if row["tipo"] in TIPOS_INTENTO)

    return {
        "global": _global_kpis(hoy),
        "totales": totales | {
            "total": len(rows),
            "ratio_kiki": round(len(kikis) / intentos * 100, 1) if intentos else None,
        },
        "promedios": {
            "calidad": _avg(calidades),
            "tiempo": _avg(tiempos),
            "calidad_tiempo": _avg([*calidades, *tiempos]),
        },
        "periodo": {
            "desde": rows[0]["fecha"] if rows else None,
            "hasta": rows[-1]["fecha"] if rows else None,
        },
        "distribucion_calidad": _score_histogram(kikis, "calidad"),
        "distribucion_tiempo": _score_histogram(kikis, "tiempo"),
        "por_dia_semana": _weekday_breakdown(rows),
        "mayor_sequia": _longest_dry_spell(_dates_of(rows, TIPO_KIKI), hoy),
        "ciclo": cycle_stats(_dates_of(rows, TIPO_MAREA), hoy),
    }


def _global_kpis(hoy: date) -> dict[str, Any]:
    """KPIs que no dependen de los filtros activos: son el estado "ahora"."""
    rows, total = crud.list_events(sort="fecha", order="asc")
    mes, anio = hoy.strftime("%Y-%m"), hoy.strftime("%Y")

    resumen: dict[str, Any] = {"hoy": hoy.isoformat(), "total_registros": total}
    for tipo, clave in CLAVE_TIPO.items():
        ultima = max(_dates_of(rows, tipo), default=None)
        del_tipo = [row for row in rows if row["tipo"] == tipo]
        resumen[f"ultimo_{clave}"] = ultima.isoformat() if ultima else None
        resumen[f"dias_sin_{clave}"] = (hoy - ultima).days if ultima else None
        resumen[f"{clave}_mes_actual"] = sum(1 for r in del_tipo if r["fecha"][:7] == mes)
        resumen[f"{clave}_anio_actual"] = sum(1 for r in del_tipo if r["fecha"][:4] == anio)

    # Alias históricos, para no romper a quien ya consume estas claves.
    resumen["ultima_marea"] = resumen["ultimo_marea"]
    resumen["kikis_mes_actual"] = resumen["kiki_mes_actual"]
    resumen["kikis_anio_actual"] = resumen["kiki_anio_actual"]
    return resumen


def _score_histogram(kikis: list[dict[str, Any]], campo: str) -> list[dict[str, int]]:
    counter = Counter(row[campo] for row in kikis)
    return [{"valor": valor, "total": counter.get(valor, 0)} for valor in range(5)]


def _weekday_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contadores: dict[int, Counter] = defaultdict(Counter)
    for row in rows:
        fecha = _parse(row["fecha"])
        if fecha:
            contadores[fecha.weekday()][row["tipo"]] += 1
    return [
        {"dia": DIAS_SEMANA[indice]}
        | {clave: contadores[indice][tipo] for tipo, clave in CLAVE_TIPO.items()}
        for indice in range(7)
    ]


def _longest_dry_spell(kiki_dates: list[date], hoy: date) -> dict[str, Any]:
    """Mayor número de días consecutivos sin ningún Kiki."""
    if not kiki_dates:
        return {"dias": None, "desde": None, "hasta": None}

    mejor = {"dias": 0, "desde": None, "hasta": None}
    for anterior, siguiente in zip(kiki_dates, kiki_dates[1:]):
        dias = (siguiente - anterior).days
        if dias > mejor["dias"]:
            mejor = {"dias": dias, "desde": anterior.isoformat(), "hasta": siguiente.isoformat()}

    # La sequía en curso también cuenta si supera al récord histórico.
    actual = (hoy - kiki_dates[-1]).days
    if actual > mejor["dias"]:
        mejor = {"dias": actual, "desde": kiki_dates[-1].isoformat(), "hasta": hoy.isoformat()}
    return mejor


def cycle_stats(marea_dates: list[date], hoy: date) -> dict[str, Any]:
    """Agrupa los días de Marea en períodos y estima duración y ciclo."""
    if not marea_dates:
        return {
            "periodos_registrados": 0,
            "duracion_media_dias": None,
            "ciclo_medio_dias": None,
            "ultimo_periodo_inicio": None,
            "dia_del_ciclo": None,
            "proxima_prevista": None,
            "dias_para_proxima": None,
        }

    periodos: list[list[date]] = [[marea_dates[0]]]
    for fecha in marea_dates[1:]:
        if (fecha - periodos[-1][-1]).days <= GAP_MISMO_PERIODO:
            periodos[-1].append(fecha)
        else:
            periodos.append([fecha])

    duraciones = [(grupo[-1] - grupo[0]).days + 1 for grupo in periodos]
    inicios = [grupo[0] for grupo in periodos]
    ciclos = [
        (siguiente - anterior).days
        for anterior, siguiente in zip(inicios, inicios[1:])
        if CICLO_MIN_DIAS <= (siguiente - anterior).days <= CICLO_MAX_DIAS
    ]

    ultimo_inicio = inicios[-1]
    ciclo_medio = _avg([float(dias) for dias in ciclos])
    proxima = ultimo_inicio + timedelta(days=round(ciclo_medio)) if ciclo_medio else None

    return {
        "periodos_registrados": len(periodos),
        "duracion_media_dias": _avg([float(dias) for dias in duraciones]),
        "ciclo_medio_dias": ciclo_medio,
        "ultimo_periodo_inicio": ultimo_inicio.isoformat(),
        "dia_del_ciclo": (hoy - ultimo_inicio).days + 1,
        "proxima_prevista": proxima.isoformat() if proxima else None,
        "dias_para_proxima": (proxima - hoy).days if proxima else None,
    }


def _acumular(registro: dict[str, Any], row: dict[str, Any]) -> None:
    """Suma un evento al bucket de su periodo, con sus valoraciones si las tiene."""
    clave = CLAVE_TIPO.get(row["tipo"])
    if not clave:
        return
    registro[clave] += 1
    if row["tipo"] == TIPO_KIKI:
        registro["_calidad"].append(row["calidad"])
        registro["_tiempo"].append(row["tiempo"])


def monthly(year: int, filters: Optional[EventFilters] = None) -> list[dict[str, Any]]:
    filters = filters or EventFilters()
    filters.year = year
    rows = _fetch(filters)

    acumulado: dict[int, dict[str, Any]] = {
        mes: {"mes": mes, "etiqueta": MESES[mes - 1], "_calidad": [], "_tiempo": []}
             | _contador_vacio()
        for mes in range(1, 13)
    }
    for row in rows:
        fecha = _parse(row["fecha"])
        if not fecha:
            continue
        _acumular(acumulado[fecha.month], row)

    resultado = []
    for mes in range(1, 13):
        registro = acumulado[mes]
        registro["calidad_media"] = _avg(registro.pop("_calidad"))
        registro["tiempo_medio"] = _avg(registro.pop("_tiempo"))
        resultado.append(registro)
    return resultado


def yearly(filters: Optional[EventFilters] = None) -> list[dict[str, Any]]:
    base = filters or EventFilters()
    base.year = None
    rows = _fetch(base)

    acumulado: dict[int, dict[str, Any]] = {}
    for row in rows:
        fecha = _parse(row["fecha"])
        if not fecha:
            continue
        registro = acumulado.setdefault(
            fecha.year,
            {"anio": fecha.year, "_calidad": [], "_tiempo": []} | _contador_vacio(),
        )
        _acumular(registro, row)

    resultado = []
    for anio in sorted(acumulado):
        registro = acumulado[anio]
        registro["calidad_media"] = _avg(registro.pop("_calidad"))
        registro["tiempo_medio"] = _avg(registro.pop("_tiempo"))
        resultado.append(registro)
    return resultado


def breakdown(filters: Optional[EventFilters] = None) -> dict[str, Any]:
    """Reparto por motivación y por pretexto.

    Sólo entran las categorías que llevan esos campos: la Gayola es en
    solitario y la Marea no es un encuentro, así que ninguna aparece aquí.
    """
    rows = [row for row in _fetch(filters) if row["tipo"] in TIPOS_CON_CONTEXTO]
    claves = [CLAVE_TIPO[tipo] for tipo in TIPOS_CON_CONTEXTO]

    def agrupar(campo: str) -> list[dict[str, Any]]:
        acumulado: dict[str, dict[str, Any]] = {}
        for row in rows:
            clave = row.get(campo) or "Sin especificar"
            registro = acumulado.setdefault(
                clave,
                {"clave": clave, "_calidad": []} | {c: 0 for c in claves},
            )
            registro[CLAVE_TIPO[row["tipo"]]] += 1
            if row["tipo"] == TIPO_KIKI:
                registro["_calidad"].append(row["calidad"])

        salida = []
        for registro in acumulado.values():
            registro["total"] = sum(registro[c] for c in claves)
            registro["calidad_media"] = _avg(registro.pop("_calidad"))
            salida.append(registro)
        return sorted(salida, key=lambda item: item["total"], reverse=True)

    return {
        "motivacion": agrupar("motivacion"),
        "pretexto": agrupar("pretexto"),
        "tags": por_tags(filters),
    }


def por_tags(filters: Optional[EventFilters] = None) -> list[dict[str, Any]]:
    """Cuántos Kikis lleva cada etiqueta y qué calidad media tienen.

    Un registro suma en todas sus etiquetas, así que los totales no cuadran
    con el número de Kikis: es un reparto por etiqueta, no una partición.
    """
    acumulado: dict[str, dict[str, Any]] = {}
    for row in _fetch(filters):
        for etiqueta in row.get("tags") or []:
            registro = acumulado.setdefault(
                etiqueta, {"clave": etiqueta, "total": 0, "_calidad": [], "_tiempo": []}
            )
            registro["total"] += 1
            registro["_calidad"].append(row["calidad"])
            registro["_tiempo"].append(row["tiempo"])

    salida = []
    for registro in acumulado.values():
        registro["calidad_media"] = _avg(registro.pop("_calidad"))
        registro["tiempo_medio"] = _avg(registro.pop("_tiempo"))
        salida.append(registro)
    return sorted(salida, key=lambda item: item["total"], reverse=True)


def calendar(year: int, month: Optional[int] = None,
             filters: Optional[EventFilters] = None) -> dict[str, Any]:
    """Eventos agrupados por día, listos para pintar el calendario."""
    filters = filters or EventFilters()
    filters.year = year
    rows = _fetch(filters)
    if month:
        prefijo = f"{year:04d}-{month:02d}"
        rows = [row for row in rows if row["fecha"].startswith(prefijo)]

    dias: dict[str, dict[str, Any]] = {}
    for row in rows:
        dia = dias.setdefault(
            row["fecha"],
            {"fecha": row["fecha"], "tipos": [], "calidad_max": 0,
             "tiempo_max": 0, "eventos": []},
        )
        if row["tipo"] not in dia["tipos"]:
            dia["tipos"].append(row["tipo"])
        dia["calidad_max"] = max(dia["calidad_max"], row["calidad"])
        dia["tiempo_max"] = max(dia["tiempo_max"], row["tiempo"])
        dia["eventos"].append(row)

    return {"year": year, "month": month, "dias": dias}
