#!/usr/bin/env python3
"""Importa varias rúbricas en lote, una a una y SIEMPRE con revisión.

Para cada rúbrica usa la URL de su tarea si la trae (moodle.url_tarea; en el maestro,
tarea["moodle"]["url_tarea"]); si no, la pide (URL o id). Después ejecuta importar_rubrica.py sin
--sin-revisar, de modo que el script se detiene a pedir confirmación antes de guardar.

Formatos de entrada (.json):
  · un array de rúbricas:            [ {formato_version: 1, ...}, {...} ]
  · un objeto {"rubricas": [ ... ]}
  · el maestro rubricas_ud2.json     {"tareas": [ ... ]} (se convierte como generar_json.py)
  · una única rúbrica
Un Excel (.xlsx) cuenta como una rúbrica y se convierte con rub_xlsx2json.py.

    python importar_lote.py rubricas.json
    python importar_lote.py rubricas_ud2.json --tarea 1 --tarea 3 --moodle https://TU-MOODLE
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from generar_json import convertir
from importar_rubrica import ErrorRubrica, cargar_rubrica, normalizar_url_tarea, resumen

AQUI = Path(__file__).resolve().parent
IMPORTADOR = AQUI / "importar_rubrica.py"
XLSX2JSON = AQUI / "rub_xlsx2json.py"


def extraer_rubricas(ruta: Path, unidad: str, tareas: list[int] | None) -> list[tuple[str, dict]]:
    """Devuelve [(etiqueta, rúbrica)] según el formato del fichero."""
    if ruta.suffix.lower() in (".xlsx", ".xlsm"):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "r.json"
            r = subprocess.run([sys.executable, str(XLSX2JSON), str(ruta), str(destino)])
            if r.returncode != 0:
                raise SystemExit(f"No se pudo convertir {ruta}.")
            return [(ruta.stem, json.loads(destino.read_text(encoding="utf-8")))]

    datos = json.loads(ruta.read_text(encoding="utf-8-sig"))
    if isinstance(datos, dict) and "tareas" in datos:
        return [
            (f"Tarea {t['numero']}", convertir(t, unidad))
            for t in datos["tareas"]
            if not tareas or t["numero"] in tareas
        ]
    if isinstance(datos, dict) and "rubricas" in datos:
        datos = datos["rubricas"]
    if isinstance(datos, dict):
        datos = [datos]
    if not isinstance(datos, list) or not all(isinstance(d, dict) for d in datos):
        raise SystemExit(f"{ruta}: formato no reconocido (se esperaba un array de rúbricas).")
    return [(f"#{i}", d) for i, d in enumerate(datos, 1)]


def pedir_url(base: str | None) -> str | None:
    """Pide la tarea. Devuelve None si se salta esta rúbrica; 'q' aborta el lote."""
    print("  Pega la URL de la tarea (…/mod/assign/view.php?id=NNN) o su id.")
    print("  Intro = saltar esta rúbrica · q = terminar el lote.")
    while True:
        texto = input("  URL o id: ").strip()
        if not texto:
            return None
        if texto.lower() == "q":
            raise KeyboardInterrupt
        try:
            return normalizar_url_tarea(texto, base)
        except ErrorRubrica as e:
            print(f"  ✗ {e}")
            if texto.isdigit() and not base:
                base = input("  URL raíz de Moodle (https://TU-MOODLE): ").strip() or None


def main() -> int:
    ap = argparse.ArgumentParser(description="Importa rúbricas en lote, una a una y siempre con revisión.")
    ap.add_argument("fichero", type=Path, help="JSON con varias rúbricas (o Excel).")
    ap.add_argument("--moodle", help="URL raíz de Moodle, para poder indicar las tareas solo por su id.")
    ap.add_argument("--tarea", type=int, action="append",
                    help="Solo con el maestro rubricas_ud2.json: número de tarea (repetible).")
    ap.add_argument("--unidad", default="UD2", help="Prefijo del nombre con el maestro (por defecto UD2).")
    ap.add_argument("--reemplazar", action="store_true",
                    help="Permite sustituir rúbricas existentes (con confirmación en cada una).")
    ap.add_argument("--borrador", action="store_true")
    ap.add_argument("--nueva-sesion", action="store_true", help="Solo se aplica a la primera rúbrica.")
    ap.add_argument("--navegador", default="chromium", choices=["chromium", "chrome", "msedge"])
    ap.add_argument("--perfil", type=Path)
    args = ap.parse_args()

    elementos = extraer_rubricas(args.fichero, args.unidad, args.tarea)
    if not elementos:
        print("No hay rúbricas que importar.")
        return 1

    with tempfile.TemporaryDirectory(prefix="lote_rubricas_") as tmp:
        # Valida todas antes de abrir nada
        preparadas = []
        for i, (etiqueta, datos) in enumerate(elementos, 1):
            ruta = Path(tmp) / f"rubrica_{i:02d}.json"
            ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                preparadas.append((etiqueta, cargar_rubrica(ruta), ruta))
            except ErrorRubrica as e:
                print(f"✗ {etiqueta}: {e}")
                return 1
        print(f"Lote de {len(preparadas)} rúbricas válidas. Cada una se revisará antes de guardarse.")

        resultados: list[tuple[str, str]] = []
        primera = True
        try:
            for i, (etiqueta, rubrica, ruta) in enumerate(preparadas, 1):
                print(f"\n=== [{i}/{len(preparadas)}] {etiqueta} ===")
                print(resumen(rubrica))
                url = None
                if rubrica.url:
                    try:
                        url = normalizar_url_tarea(rubrica.url, args.moodle)
                        print(f"  Tarea indicada en la rúbrica: {url}")
                    except ErrorRubrica as e:
                        print(f"  ✗ moodle.url_tarea no válida: {e}")
                if url is None:
                    url = pedir_url(args.moodle)
                if url is None:
                    resultados.append((rubrica.nombre, "saltada"))
                    continue
                cmd = [sys.executable, str(IMPORTADOR), str(ruta), "--url", url,
                       "--navegador", args.navegador]
                if args.moodle:
                    cmd += ["--moodle", args.moodle]
                if args.perfil:
                    cmd += ["--perfil", str(args.perfil)]
                if args.reemplazar:
                    cmd.append("--reemplazar")
                if args.borrador:
                    cmd.append("--borrador")
                if args.nueva_sesion and primera:
                    cmd.append("--nueva-sesion")
                primera = False
                # Sin --sin-revisar: importar_rubrica.py siempre pide confirmación
                codigo = subprocess.run(cmd, cwd=AQUI).returncode
                resultados.append((rubrica.nombre, "OK" if codigo == 0 else f"con errores ({codigo})"))
        except (KeyboardInterrupt, EOFError):
            print("\nLote interrumpido.")

    print("\nResumen del lote:")
    for nombre, estado in resultados:
        print(f"  · {nombre}: {estado}")
    restantes = len(preparadas) - len(resultados)
    if restantes > 0:
        print(f"  · {restantes} sin procesar")
    return 0 if all(e in ("OK", "saltada") for _, e in resultados) and restantes <= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
