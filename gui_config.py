"""Preferencias de la GUI en un fichero .env (CLAVE=valor) junto a los scripts."""
from __future__ import annotations

from pathlib import Path

FICHERO_ENV = Path(__file__).resolve().parent / ".env"


def leer(ruta: Path = FICHERO_ENV) -> dict[str, str]:
    datos: dict[str, str] = {}
    try:
        lineas = ruta.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return datos
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        datos[clave.strip()] = valor.strip().strip('"').strip("'")
    return datos


def guardar(cambios: dict[str, str], ruta: Path = FICHERO_ENV) -> None:
    """Actualiza solo las claves indicadas y conserva el resto del fichero."""
    try:
        lineas = ruta.read_text(encoding="utf-8-sig").splitlines() if ruta.exists() else []
    except OSError:
        lineas = []
    pendientes = dict(cambios)
    salida = []
    for linea in lineas:
        clave = linea.split("=", 1)[0].strip() if "=" in linea and not linea.lstrip().startswith("#") else None
        if clave in pendientes:
            salida.append(f"{clave}={pendientes.pop(clave)}")
        else:
            salida.append(linea)
    salida += [f"{k}={v}" for k, v in pendientes.items()]
    try:
        ruta.write_text("\n".join(salida) + "\n", encoding="utf-8")
    except OSError:
        pass  # sin permisos de escritura: las preferencias simplemente no se recuerdan


def a_bool(valor: str | None, defecto: bool) -> bool:
    if valor is None:
        return defecto
    return valor.strip().lower() in ("1", "true", "yes", "si", "sÃ­", "s")
