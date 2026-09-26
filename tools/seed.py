"""Genera datos de ejemplo para probar la aplicación.

    python tools/seed.py [--meses 18] [--reset]

No se usa en producción: sirve para ver el dashboard con contenido realista.
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402
from app.crud import create_event  # noqa: E402
from app.schemas import EventCreate  # noqa: E402

PRETEXTOS = ["Desatranque", "Cumpleaños", "Calentura", "Necesidad",
             "Aniversario", "Reconciliación", "Rutina", "Viaje"]
MOTIVACIONES = ["Propia", "Ajena", "Ambos"]
NOTAS = ["", "", "", "Buen día", "Con prisas", "Fin de semana",
         "Después de cenar", "Cansancio", "Sorpresa"]


def generar(meses: int, semilla: int = 7) -> list[EventCreate]:
    aleatorio = random.Random(semilla)
    hoy = date.today()
    inicio = hoy - timedelta(days=meses * 30)
    eventos: list[EventCreate] = []

    # Ciclo menstrual: períodos de 4-6 días cada 26-32 días.
    cursor = inicio + timedelta(days=aleatorio.randint(0, 20))
    while cursor < hoy:
        for desplazamiento in range(aleatorio.randint(4, 6)):
            dia = cursor + timedelta(days=desplazamiento)
            if dia < hoy:
                eventos.append(EventCreate(fecha=dia, tipo="Marea"))
        cursor += timedelta(days=aleatorio.randint(26, 32))

    # Encuentros y desencuentros repartidos por el período.
    dia = inicio
    while dia < hoy:
        # Más probabilidad en fin de semana.
        probabilidad = 0.30 if dia.weekday() >= 4 else 0.14
        if aleatorio.random() < probabilidad:
            if aleatorio.random() < 0.78:
                eventos.append(
                    EventCreate(
                        fecha=dia,
                        tipo="Kiki",
                        pretexto=aleatorio.choice(PRETEXTOS),
                        motivacion=aleatorio.choice(MOTIVACIONES),
                        calidad=aleatorio.choices([1, 2, 3, 4], [1, 3, 5, 4])[0],
                        tiempo=aleatorio.choices([1, 2, 3, 4], [2, 4, 4, 2])[0],
                        observaciones=aleatorio.choice(NOTAS) or None,
                    )
                )
            else:
                eventos.append(
                    EventCreate(
                        fecha=dia,
                        tipo="No Kiki",
                        pretexto=aleatorio.choice(["Cansancio", "Discusión", "N/A"]),
                        motivacion=aleatorio.choice(MOTIVACIONES),
                        observaciones=aleatorio.choice(NOTAS) or None,
                    )
                )
        dia += timedelta(days=1)

    return eventos


def main() -> None:
    parser = argparse.ArgumentParser(description="Datos de ejemplo para Kiki App")
    parser.add_argument("--meses", type=int, default=18)
    parser.add_argument("--reset", action="store_true", help="Vacía la tabla antes")
    argumentos = parser.parse_args()

    db.init_db()
    if argumentos.reset:
        with db.connect() as conn:
            conn.execute("DELETE FROM events")
        print("Tabla vaciada")

    eventos = generar(argumentos.meses)
    for evento in eventos:
        create_event(evento)
    print(f"{len(eventos)} registros creados")


if __name__ == "__main__":
    main()
