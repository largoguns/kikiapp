"""Contrato de la API REST."""

from __future__ import annotations


def crear(cliente, **campos):
    cuerpo = {"fecha": "2026-03-10", "tipo": "Kiki", "calidad": 3, "tiempo": 2}
    cuerpo.update(campos)
    respuesta = cliente.post("/api/events", json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_ciclo_completo_crud(cliente):
    creado = crear(cliente, pretexto="  Calentura  ", motivacion="propia",
                   observaciones="  nota  ")
    # Los textos se recortan y la motivación se normaliza.
    assert creado["pretexto"] == "Calentura"
    assert creado["motivacion"] == "Propia"
    assert creado["observaciones"] == "nota"

    identificador = creado["id"]
    assert cliente.get(f"/api/events/{identificador}").json()["id"] == identificador

    actualizado = cliente.put(
        f"/api/events/{identificador}",
        json={"fecha": "2026-03-11", "tipo": "Kiki", "calidad": 4, "tiempo": 4},
    ).json()
    assert actualizado["fecha"] == "2026-03-11"
    assert actualizado["calidad"] == 4
    assert actualizado["pretexto"] is None

    assert cliente.delete(f"/api/events/{identificador}").status_code == 204
    assert cliente.get(f"/api/events/{identificador}").status_code == 404


def test_solo_los_kiki_se_puntuan(cliente):
    no_kiki = crear(cliente, tipo="No Kiki", calidad=4, tiempo=4)
    marea = crear(cliente, tipo="Marea", calidad=3, tiempo=3)
    assert (no_kiki["calidad"], no_kiki["tiempo"]) == (0, 0)
    assert (marea["calidad"], marea["tiempo"]) == (0, 0)


def test_valores_fuera_de_rango_se_rechazan(cliente):
    assert cliente.post(
        "/api/events", json={"fecha": "2026-03-10", "tipo": "Kiki", "calidad": 9}
    ).status_code == 422
    assert cliente.post(
        "/api/events", json={"fecha": "2026-03-10", "tipo": "Inventado"}
    ).status_code == 422
    assert cliente.post(
        "/api/events", json={"fecha": "no-es-fecha", "tipo": "Kiki"}
    ).status_code == 422


def test_filtros_y_paginacion(cliente):
    crear(cliente, fecha="2025-01-05", calidad=1, tiempo=1, motivacion="Propia")
    crear(cliente, fecha="2026-01-05", calidad=4, tiempo=4, motivacion="Ajena")
    crear(cliente, fecha="2026-02-05", tipo="No Kiki", motivacion="Ajena")

    assert cliente.get("/api/events?year=2026").json()["total"] == 2
    assert cliente.get("/api/events?min_calidad=4").json()["total"] == 1
    assert cliente.get("/api/events?motivacion=Ajena").json()["total"] == 2
    assert cliente.get("/api/events?tipo=No+Kiki").json()["total"] == 1

    pagina = cliente.get("/api/events?limit=1&offset=0&sort=fecha&order=asc").json()
    assert pagina["total"] == 3 and len(pagina["items"]) == 1
    assert pagina["items"][0]["fecha"] == "2025-01-05"


def test_busqueda_libre(cliente):
    crear(cliente, observaciones="cena romántica")
    crear(cliente, fecha="2026-04-01")
    assert cliente.get("/api/events?q=romántica").json()["total"] == 1


def test_opciones_incluye_pretextos_usados(cliente):
    crear(cliente, pretexto="Escapada")
    opciones = cliente.get("/api/options").json()
    assert "Escapada" in opciones["pretextos"]
    assert "Desatranque" in opciones["pretextos"]  # sugerencia por defecto
    assert opciones["years"] == [2026]


def test_resumen_y_series(cliente):
    crear(cliente, fecha="2026-03-01", calidad=4, tiempo=2)
    crear(cliente, fecha="2026-03-02", tipo="No Kiki")

    resumen = cliente.get("/api/stats/summary?year=2026").json()
    assert resumen["totales"] == {
        "kiki": 1, "no_kiki": 1, "marea": 0, "total": 2, "ratio_kiki": 50.0
    }
    assert resumen["promedios"]["calidad"] == 4
    assert resumen["global"]["ultimo_kiki"] == "2026-03-01"

    meses = cliente.get("/api/stats/monthly?year=2026").json()["meses"]
    assert len(meses) == 12
    assert meses[2]["kiki"] == 1 and meses[2]["no_kiki"] == 1

    calendario = cliente.get("/api/stats/calendar?year=2026&month=3").json()
    assert set(calendario["dias"]) == {"2026-03-01", "2026-03-02"}
    assert calendario["dias"]["2026-03-01"]["calidad_max"] == 4


def test_sin_importaciones_previas(cliente):
    assert cliente.get("/api/import").json()["ultima_importacion"] is None


def test_health_y_vistas(cliente):
    assert cliente.get("/api/health").json()["status"] == "ok"
    assert cliente.get("/").status_code == 200
    assert cliente.get("/m").status_code == 200
    assert cliente.get("/manifest.webmanifest").status_code == 200
    assert cliente.get("/sw.js").status_code == 200
