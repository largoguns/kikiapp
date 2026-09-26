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
        "kiki": 1, "no_kiki": 1, "gayola": 0, "marea": 0,
        "total": 2, "ratio_kiki": 50.0,
    }
    assert resumen["promedios"]["calidad"] == 4
    assert resumen["global"]["ultimo_kiki"] == "2026-03-01"

    meses = cliente.get("/api/stats/monthly?year=2026").json()["meses"]
    assert len(meses) == 12
    assert meses[2]["kiki"] == 1 and meses[2]["no_kiki"] == 1

    calendario = cliente.get("/api/stats/calendar?year=2026&month=3").json()
    assert set(calendario["dias"]) == {"2026-03-01", "2026-03-02"}
    assert calendario["dias"]["2026-03-01"]["calidad_max"] == 4


def test_gayola_es_un_evento_en_solitario(cliente):
    """Ni se valora ni lleva con quién ni por qué: es en solitario."""
    gayola = crear(cliente, tipo="Gayola", calidad=4, tiempo=4,
                   motivacion="Ambos", pretexto="Calentura",
                   observaciones="esto sí se guarda")
    assert (gayola["calidad"], gayola["tiempo"]) == (0, 0)
    assert gayola["pretexto"] is None
    assert gayola["motivacion"] is None
    assert gayola["observaciones"] == "esto sí se guarda"


def test_gayola_es_categoria_aparte_en_las_metricas(cliente):
    crear(cliente, tipo="Gayola")

    crear(cliente, fecha="2026-03-01", calidad=2, tiempo=2)      # Kiki
    crear(cliente, fecha="2026-03-02", tipo="No Kiki")

    resumen = cliente.get("/api/stats/summary").json()
    assert resumen["totales"]["gayola"] == 1
    # Ni entra en el acierto (1 de 2 intentos) ni toca las medias de calidad.
    assert resumen["totales"]["ratio_kiki"] == 50.0
    assert resumen["promedios"]["calidad"] == 2

    # Tiene su propia métrica, independiente de la del Kiki.
    assert resumen["global"]["ultimo_gayola"] == "2026-03-10"
    assert resumen["global"]["dias_sin_gayola"] is not None
    assert resumen["global"]["dias_sin_kiki"] != resumen["global"]["dias_sin_gayola"]

    # Y no aparece en el reparto por motivación: no tiene ese campo.
    reparto = cliente.get("/api/stats/breakdown").json()
    for dimension in ("motivacion", "pretexto"):
        assert all("gayola" not in item for item in reparto[dimension])
    assert sum(item["total"] for item in reparto["motivacion"]) == 2  # Kiki + No Kiki


def test_alta_por_rango_de_fechas(cliente):
    respuesta = cliente.post("/api/events/rango", json={
        "fecha": "2026-04-10", "hasta": "2026-04-15", "tipo": "Marea",
    })
    assert respuesta.status_code == 201
    assert respuesta.json()["creados"] == 6
    assert cliente.get("/api/events?tipo=Marea").json()["total"] == 6


def test_rango_solapado_no_duplica_dias(cliente):
    cliente.post("/api/events/rango", json={
        "fecha": "2026-04-10", "hasta": "2026-04-15", "tipo": "Marea"})
    # Ampliar un período ya registrado a medias sólo añade lo que falta.
    segundo = cliente.post("/api/events/rango", json={
        "fecha": "2026-04-13", "hasta": "2026-04-18", "tipo": "Marea"}).json()
    assert (segundo["creados"], segundo["omitidos"]) == (3, 3)
    assert cliente.get("/api/events?tipo=Marea").json()["total"] == 9


def test_rango_invalido_se_rechaza(cliente):
    invertido = cliente.post("/api/events/rango", json={
        "fecha": "2026-04-15", "hasta": "2026-04-10", "tipo": "Marea"})
    assert invertido.status_code == 422

    excesivo = cliente.post("/api/events/rango", json={
        "fecha": "2026-01-01", "hasta": "2026-12-31", "tipo": "Marea"})
    assert excesivo.status_code == 422


def test_tags_solo_en_los_kiki(cliente):
    kiki = crear(cliente, tags=["  Perrito ", "perrito", "Cunilingus", ""])
    # Se recortan, se quitan repetidos sin distinguir mayúsculas y se ordena
    # como se escribió.
    assert kiki["tags"] == ["Perrito", "Cunilingus"]
    # Las observaciones conviven con las etiquetas.
    assert crear(cliente, fecha="2026-03-11", tags=["Anal"],
                 observaciones="una nota")["observaciones"] == "una nota"

    for tipo in ("No Kiki", "Gayola", "Marea"):
        otro = crear(cliente, fecha="2026-03-12", tipo=tipo, tags=["Anal"])
        assert otro["tags"] == [], tipo


def test_tags_se_pueden_filtrar(cliente):
    crear(cliente, fecha="2026-04-01", tags=["Perrito", "Cunilingus"])
    crear(cliente, fecha="2026-04-02", tags=["Perrito", "Misionero"])
    crear(cliente, fecha="2026-04-03", tags=["Ducha"])

    assert cliente.get("/api/events?tag=Perrito").json()["total"] == 2
    assert cliente.get("/api/events?tag=Ducha").json()["total"] == 1
    # Varias etiquetas: basta con que lleve alguna.
    assert cliente.get("/api/events?tag=Cunilingus&tag=Ducha").json()["total"] == 2
    assert cliente.get("/api/events?tag=Inexistente").json()["total"] == 0


def test_tags_en_opciones_y_reparto(cliente):
    crear(cliente, fecha="2026-04-01", calidad=4, tags=["Perrito"])
    crear(cliente, fecha="2026-04-02", calidad=2, tags=["Perrito", "Ducha"])

    opciones = cliente.get("/api/options").json()
    # Primero las usadas, por frecuencia; detrás las sugerencias.
    assert opciones["tags"][0] == "Perrito"
    assert "Felación" in opciones["tags"]

    reparto = cliente.get("/api/stats/breakdown").json()["tags"]
    perrito = next(item for item in reparto if item["clave"] == "Perrito")
    assert perrito["total"] == 2
    assert perrito["calidad_media"] == 3      # (4 + 2) / 2


def test_al_editar_se_pueden_cambiar_los_tags(cliente):
    creado = crear(cliente, tags=["Perrito"])
    actualizado = cliente.put(f"/api/events/{creado['id']}", json={
        "fecha": "2026-03-10", "tipo": "Kiki", "calidad": 3, "tiempo": 2,
        "tags": ["Vaquera", "Juguetes"],
    }).json()
    assert actualizado["tags"] == ["Vaquera", "Juguetes"]


def test_normalizacion_limpia_filas_antiguas(cliente):
    """Las reglas por tipo han cambiado: al arrancar se ponen al día."""
    from app import db

    # Fila escrita a mano como la dejaría una versión anterior de la app.
    with db.connect() as conexion:
        conexion.execute(
            "INSERT INTO events (fecha, tipo, pretexto, motivacion, calidad, tiempo,"
            " tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("2026-02-02", "Gayola", "Calentura", "Propia", 4, 3,
             '["Anal"]', "x", "x"),
        )

    assert db.normalizar_por_tipo() == 1
    with db.connect() as conexion:
        fila = conexion.execute(
            "SELECT * FROM events WHERE fecha = '2026-02-02'").fetchone()
    assert fila["pretexto"] is None and fila["motivacion"] is None
    assert (fila["calidad"], fila["tiempo"]) == (0, 0)
    assert fila["tags"] == "[]"

    # Idempotente: una segunda pasada ya no toca nada.
    assert db.normalizar_por_tipo() == 0


def test_sin_importaciones_previas(cliente):
    assert cliente.get("/api/import").json()["ultima_importacion"] is None


def test_health_y_vistas(cliente):
    assert cliente.get("/api/health").json()["status"] == "ok"
    assert cliente.get("/").status_code == 200
    assert cliente.get("/m").status_code == 200
    assert cliente.get("/manifest.webmanifest").status_code == 200
    assert cliente.get("/sw.js").status_code == 200
