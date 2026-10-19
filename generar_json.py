#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera los JSON de rúbrica (formato de importar_rubrica.py) a partir del
fichero maestro rubricas_ud2.json, que contiene todas las tareas de la unidad.

    python generar_json.py rubricas_ud2.json --tarea 1      # solo la tarea 1
    python generar_json.py rubricas_ud2.json                # todas
"""
import argparse
import json
from pathlib import Path

NOMBRES_NIVEL = ["Insuficiente", "Adecuado", "Excelente"]


def convertir(t: dict, unidad: str) -> dict:
    criterios = []
    for c in t["criterios"]:
        puntos = [0, c["peso"] // 2, c["peso"]]
        criterios.append({
            "descripcion": c["nombre"],
            "niveles": [
                {"nombre": NOMBRES_NIVEL[i], "puntos": puntos[i], "definicion": c["niveles"][i]}
                for i in range(3)
            ],
        })
    descripcion = t["descripcion"]
    if t.get("nota"):
        descripcion += "\n" + t["nota"]
    return {
        "formato_version": 1,
        "nombre": f"{unidad} · Tarea {t['numero']} · {t['titulo']}",
        "descripcion": descripcion,
        "puntuacion_maxima": sum(c["peso"] for c in t["criterios"]),
        # Igual que en el esquema de la rúbrica: tarea["moodle"]["url_tarea"] (o tarea["url_tarea"])
        "moodle": {"url_tarea": (t.get("moodle") or {}).get("url_tarea") or t.get("url_tarea")},
        "opciones": {
            "ordenar_niveles_ascendente": True,
            "mostrar_descripcion_alumno": True,
            "mostrar_puntos_alumno": True,
            "permitir_comentarios": True,
            "mostrar_comentarios_alumno": True,
        },
        "criterios": criterios,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("maestro", type=Path)
    ap.add_argument("--tarea", type=int, action="append", help="Número de tarea (repetible). Sin él, todas.")
    ap.add_argument("--unidad", default="UD2")
    ap.add_argument("--salida", type=Path, default=Path("."))
    a = ap.parse_args()

    datos = json.loads(a.maestro.read_text(encoding="utf-8"))
    a.salida.mkdir(parents=True, exist_ok=True)
    for t in datos["tareas"]:
        if a.tarea and t["numero"] not in a.tarea:
            continue
        destino = a.salida / f"rubrica_tarea{t['numero']}.json"
        destino.write_text(json.dumps(convertir(t, a.unidad), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"✓ {destino}")


if __name__ == "__main__":
    main()
