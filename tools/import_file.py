"""Importa el histórico desde un .xlsx o .csv.

    python tools/import_file.py Kiki.xlsx --simular
    python tools/import_file.py Kiki.xlsx
    python tools/import_file.py Kiki.xlsx --modo reemplazar

Equivale al botón «Importar» del dashboard; existe para poder hacerlo desde
la consola del contenedor sin pasar por el navegador.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402
from app.services import importer  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Importar histórico a Kiki App")
    parser.add_argument("fichero", type=Path)
    parser.add_argument("--modo", choices=("combinar", "reemplazar"), default="combinar")
    parser.add_argument("--hoja", help="Forzar una pestaña concreta del libro")
    parser.add_argument("--simular", action="store_true",
                        help="Analiza y muestra el informe sin escribir nada")
    argumentos = parser.parse_args()

    if not argumentos.fichero.is_file():
        print(f"No existe el fichero {argumentos.fichero}", file=sys.stderr)
        return 1

    db.init_db()
    try:
        informe = importer.importar(
            argumentos.fichero.read_bytes(),
            argumentos.fichero.name,
            modo=argumentos.modo,
            simular=argumentos.simular,
            hoja=argumentos.hoja,
        )
    except importer.ImportError_ as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    informe.pop("muestra", None)
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
