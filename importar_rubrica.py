#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
importar_rubrica.py
===================
Crea una rúbrica de Moodle (método de calificación avanzada «Rúbrica» de una
Tarea / mod_assign) a partir de un fichero JSON, rellenando el editor web de
Moodle con un navegador controlado por Playwright.

- No necesita plugins ni servicios web: hace lo mismo que harías a mano.
- No se autentica: abre el navegador y tú inicias sesión con tus datos.
  La sesión se guarda en un perfil local, así que normalmente solo tendrás
  que iniciar sesión la primera vez.

Uso básico:
    python importar_rubrica.py rubrica_tarea1.json
    python importar_rubrica.py rubrica_tarea1.json --url "https://aula.ejemplo.es/mod/assign/view.php?id=1234"
    python importar_rubrica.py rubrica_tarea1.json --reemplazar     # permite sustituir una rúbrica existente
    python importar_rubrica.py rubrica_tarea1.json --sin-revisar    # no pide confirmación antes de guardar

Comportamiento conservador por defecto (sin parámetros):
    - Siempre se detiene antes de guardar para que revises la rúbrica y confirmes.
    - Nunca reemplaza una rúbrica existente: si la tarea ya tiene una, no toca nada.
    - Con --reemplazar, además pide confirmación expresa antes de sustituir la existente;
      no se borra nada hasta que confirmas el guardado.
    python importar_rubrica.py rubrica_*.json                        # varias rúbricas seguidas
    python importar_rubrica.py rubrica_tarea1.json --solo-validar   # comprueba el JSON sin abrir Moodle

Requisitos:
    pip install playwright
    python -m playwright install chromium
"""

from __future__ import annotations

import argparse
from html import escape
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

FORMATO_VERSION = 1
PERFIL_POR_DEFECTO = Path.home() / ".moodle_rubricas_perfil"

# Opciones de la rúbrica de Moodle admitidas en el JSON (bloque "opciones").
# Clave JSON -> nombre del campo en el formulario de Moodle.
OPCIONES_MOODLE = {
    "ordenar_niveles_ascendente": "sortlevelsasc",
    "bloquear_cero_puntos": "lockzeropoints",
    "mostrar_definicion_siempre": "alwaysshowdefinition",
    "mostrar_descripcion_profesor": "showdescriptionteacher",
    "mostrar_descripcion_alumno": "showdescriptionstudent",
    "mostrar_puntos_profesor": "showscoreteacher",
    "mostrar_puntos_alumno": "showscorestudent",
    "permitir_comentarios": "enableremarks",
    "mostrar_comentarios_alumno": "showremarksstudent",
}


# --------------------------------------------------------------------------
# Modelo y validación del JSON
# --------------------------------------------------------------------------
@dataclass
class Nivel:
    puntos: float
    definicion: str


@dataclass
class Criterio:
    descripcion: str
    niveles: list[Nivel]


@dataclass
class Rubrica:
    nombre: str
    descripcion: str
    criterios: list[Criterio]
    opciones: dict[str, Any] = field(default_factory=dict)
    url: str | None = None
    origen: Path | None = None

    @property
    def puntuacion_maxima(self) -> float:
        return sum(max(n.puntos for n in c.niveles) for c in self.criterios)


class ErrorRubrica(Exception):
    pass


def _numero(valor: Any, donde: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErrorRubrica(f"{donde}: 'puntos' debe ser un número (recibido {valor!r}).")
    if valor < 0:
        raise ErrorRubrica(f"{donde}: 'puntos' no puede ser negativo.")
    return float(valor)


def cargar_rubrica(ruta: Path) -> Rubrica:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ErrorRubrica(f"{ruta.name}: JSON mal formado (línea {e.lineno}, columna {e.colno}): {e.msg}")

    if not isinstance(datos, dict):
        raise ErrorRubrica(f"{ruta.name}: la raíz del JSON debe ser un objeto.")
    version = datos.get("formato_version", FORMATO_VERSION)
    if version != FORMATO_VERSION:
        raise ErrorRubrica(f"{ruta.name}: formato_version {version} no soportado (se espera {FORMATO_VERSION}).")

    nombre = str(datos.get("nombre", "")).strip()
    if not nombre:
        raise ErrorRubrica(f"{ruta.name}: falta 'nombre'.")

    crit_json = datos.get("criterios")
    if not isinstance(crit_json, list) or not crit_json:
        raise ErrorRubrica(f"{ruta.name}: 'criterios' debe ser una lista con al menos un criterio.")

    criterios: list[Criterio] = []
    for i, c in enumerate(crit_json, start=1):
        donde = f"{ruta.name} › criterio {i}"
        if not isinstance(c, dict):
            raise ErrorRubrica(f"{donde}: debe ser un objeto.")
        desc = str(c.get("descripcion", "")).strip()
        if not desc:
            raise ErrorRubrica(f"{donde}: falta 'descripcion'.")
        niv_json = c.get("niveles")
        if not isinstance(niv_json, list) or len(niv_json) < 2:
            raise ErrorRubrica(f"{donde}: 'niveles' debe ser una lista con al menos 2 niveles.")
        niveles: list[Nivel] = []
        for j, n in enumerate(niv_json, start=1):
            dn = f"{donde} › nivel {j}"
            if not isinstance(n, dict):
                raise ErrorRubrica(f"{dn}: debe ser un objeto.")
            definicion = str(n.get("definicion", "")).strip()
            if not definicion:
                raise ErrorRubrica(f"{dn}: falta 'definicion'.")
            niveles.append(Nivel(_numero(n.get("puntos"), dn), definicion))
        puntos = [n.puntos for n in niveles]
        if len(set(puntos)) != len(puntos):
            raise ErrorRubrica(f"{donde}: hay niveles con los mismos puntos {puntos}; Moodle no lo admite.")
        criterios.append(Criterio(desc, niveles))

    opciones = datos.get("opciones", {}) or {}
    desconocidas = set(opciones) - set(OPCIONES_MOODLE)
    if desconocidas:
        raise ErrorRubrica(
            f"{ruta.name}: opciones desconocidas {sorted(desconocidas)}. "
            f"Válidas: {sorted(OPCIONES_MOODLE)}")

    rubrica = Rubrica(
        nombre=nombre,
        descripcion=str(datos.get("descripcion", "")).strip(),
        criterios=criterios,
        opciones=opciones,
        url=(datos.get("moodle") or {}).get("url_tarea"),
        origen=ruta,
    )

    esperada = datos.get("puntuacion_maxima")
    if esperada is not None and abs(float(esperada) - rubrica.puntuacion_maxima) > 1e-9:
        raise ErrorRubrica(
            f"{ruta.name}: 'puntuacion_maxima' es {esperada}, pero la suma de los máximos "
            f"de los criterios es {rubrica.puntuacion_maxima:g}.")
    return rubrica


def fmt_puntos(p: float) -> str:
    return str(int(p)) if float(p).is_integer() else str(p)


def resumen(r: Rubrica) -> str:
    lineas = [f"Rúbrica «{r.nombre}» · {len(r.criterios)} criterios · máximo {fmt_puntos(r.puntuacion_maxima)} p"]
    for i, c in enumerate(r.criterios, 1):
        pts = " / ".join(fmt_puntos(n.puntos) for n in c.niveles)
        lineas.append(f"  {i}. {c.descripcion}  [{pts}]")
    return "\n".join(lineas)


# --------------------------------------------------------------------------
# Identificación de la tarea en Moodle
# --------------------------------------------------------------------------
def normalizar_url_tarea(texto: str, base: str | None) -> str:
    """Acepta la URL completa de la tarea o solo su id (cmid) junto con --moodle."""
    texto = texto.strip()
    if texto.isdigit():
        if not base:
            raise ErrorRubrica("Has dado solo el id de la tarea: indica también la URL de Moodle con --moodle.")
        return f"{base.rstrip('/')}/mod/assign/view.php?id={texto}"
    u = urlparse(texto)
    if not u.scheme or not u.netloc:
        raise ErrorRubrica(f"URL no válida: {texto!r}")
    if "/mod/assign/" not in u.path or "id" not in parse_qs(u.query):
        raise ErrorRubrica(
            "La URL debe ser la de la tarea, del tipo https://.../mod/assign/view.php?id=NNN")
    return texto


def raiz_moodle(url_tarea: str) -> str:
    u = urlparse(url_tarea)
    ruta = u.path.split("/mod/assign/")[0]
    return f"{u.scheme}://{u.netloc}{ruta}"


def pedir_url(rubrica: Rubrica, base: str | None) -> str:
    print(f"\n¿En qué tarea de Moodle va la rúbrica «{rubrica.nombre}»?")
    print("  Pega la URL de la tarea (…/mod/assign/view.php?id=NNN) o solo el número id.")
    while True:
        texto = input("  URL o id: ").strip()
        try:
            return normalizar_url_tarea(texto, base)
        except ErrorRubrica as e:
            print(f"  ✗ {e}")


# --------------------------------------------------------------------------
# Automatización del navegador
# --------------------------------------------------------------------------
def confirmar(pregunta: str) -> bool:
    """Pregunta sí/no. Cualquier respuesta que no sea un sí explícito cuenta como NO."""
    try:
        return input(pregunta).strip().lower() in ("s", "si", "sí", "y", "yes")
    except EOFError:
        return False


JS_SET_VALUE = """
(el, valor) => {
  el.value = valor;
  el.dispatchEvent(new Event('input', {bubbles: true}));
  el.dispatchEvent(new Event('change', {bubbles: true}));
}
"""

JS_IDS_CRITERIOS = """
() => Array.from(document.querySelectorAll('textarea[name^="rubric[criteria]"]'))
  .map(t => (t.name.match(/^rubric\\[criteria\\]\\[([^\\]]+)\\]\\[description\\]$/) || [])[1])
  .filter(Boolean)
"""

JS_IDS_NIVELES = """
(cid) => Array.from(document.querySelectorAll('input[name^="rubric[criteria][' + cid + '][levels]"]'))
  .map(i => (i.name.match(/\\[levels\\]\\[([^\\]]+)\\]\\[score\\]$/) || [])[1])
  .filter(Boolean)
"""


class Importador:
    def __init__(self, page, revisar: bool, reemplazar: bool, borrador: bool):
        self.page = page
        self.revisar = revisar
        self.reemplazar = reemplazar
        self.borrador = borrador
        # Diálogos nativos de confirmación del editor (borrar niveles/criterios sobrantes): se aceptan.
        page.on("dialog", lambda d: d.accept())

    # ---------- utilidades ----------
    def _esperar(self):
        self.page.wait_for_load_state("domcontentloaded")
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

    def _poner(self, selector: str, valor: str):
        loc = self.page.locator(selector).first
        loc.wait_for(state="attached", timeout=10000)
        loc.evaluate(JS_SET_VALUE, valor)

    def _clic(self, selector: str):
        self.page.locator(selector).first.click()
        self._esperar()

    def _sesskey(self) -> str:
        return self.page.evaluate("() => (window.M && M.cfg && M.cfg.sesskey) || ''")

    # ---------- sesión ----------
    def abrir_tarea(self, url_tarea: str, espera_login_s: int = 600) -> tuple[int, str]:
        self.page.goto(url_tarea)
        self._esperar()
        if "/mod/assign/view.php" not in self.page.url:
            host = urlparse(url_tarea).netloc
            print("\n  → Inicia sesión en la ventana del navegador con tus datos.")
            print("    El script continuará solo en cuanto entres en Moodle.")
            for _ in range(espera_login_s):
                self.page.wait_for_timeout(1000)
                u = urlparse(self.page.url)
                if "/mod/assign/view.php" in u.path:
                    break
                # Ya autenticado pero Moodle te ha llevado a otra página (p. ej. el Área personal)
                if u.netloc == host and "/login/" not in u.path and "/auth/" not in u.path:
                    self.page.goto(url_tarea)
                    self._esperar()
            else:
                raise ErrorRubrica("No se ha completado el inicio de sesión a tiempo.")
            self._esperar()
        clases = self.page.evaluate("() => document.body.className")
        m = re.search(r"\bcontext-(\d+)\b", clases)
        if not m:
            raise ErrorRubrica("No encuentro el contexto de la tarea. ¿Es una Tarea (mod_assign) y tienes permisos de edición?")
        titulo = self.page.title()
        return int(m.group(1)), titulo

    # ---------- método de calificación ----------
    def activar_rubrica(self, base: str, contextid: int) -> int:
        sesskey = self._sesskey()
        params = {"contextid": contextid, "component": "mod_assign", "area": "submissions",
                  "setmethod": "rubric", "sesskey": sesskey}
        self.page.goto(f"{base}/grade/grading/manage.php?{urlencode(params)}")
        self._esperar()
        enlace = self.page.locator('a[href*="/grade/grading/form/rubric/edit.php"]').first
        if enlace.count() == 0:
            raise ErrorRubrica("No aparece el enlace para definir la rúbrica. ¿Tienes permiso para gestionar la calificación avanzada?")
        href = enlace.get_attribute("href") or ""
        m = re.search(r"areaid=(\d+)", href)
        if not m:
            raise ErrorRubrica("No he podido leer el areaid de la rúbrica.")
        areaid = int(m.group(1))

        borrar = self.page.locator('a[href*="deleteform="]').first
        if borrar.count() > 0:
            if not self.reemplazar:
                raise ErrorRubrica(
                    "Esta tarea ya tiene una rúbrica definida y no se ha tocado. "
                    "Usa --reemplazar si quieres sustituirla.")
            # No se borra nada aquí: la rúbrica existente se sobrescribe en el editor y el
            # cambio solo se aplica al guardar. Si se cancela, la original queda intacta.
            if self.revisar:
                print("\n  ! Esta tarea YA TIENE una rúbrica. Se sustituirá su contenido por el del JSON")
                print("    cuando confirmes el guardado. Si ya has calificado con ella, Moodle")
                print("    puede marcar esas calificaciones para revisar.")
                if not confirmar("    ¿Continuar y preparar la sustitución? [s/N] "):
                    raise ErrorRubrica("Cancelado por el usuario: la rúbrica existente se mantiene.")
            print("  · La rúbrica existente se sobrescribirá al guardar.")
        return areaid

    # ---------- editor de rúbrica ----------
    def rellenar(self, base: str, areaid: int, r: Rubrica):
        self.page.goto(f"{base}/grade/grading/form/rubric/edit.php?areaid={areaid}")
        self._esperar()
        self.page.locator("#id_name").wait_for(timeout=15000)

        self._poner("#id_name", r.nombre)
        self._poner_descripcion(r.descripcion)  # vacía = borra la descripción anterior, si la había

        for i, crit in enumerate(r.criterios):
            ids = self.page.evaluate(JS_IDS_CRITERIOS)
            if i >= len(ids):
                antes = len(ids)
                self._clic('input[name="rubric[criteria][addcriterion]"], #rubric-criteria-addcriterion')
                self.page.wait_for_function(f"() => ({JS_IDS_CRITERIOS})().length > {antes}", timeout=10000)
                ids = self.page.evaluate(JS_IDS_CRITERIOS)
            cid = ids[i]
            self._poner(f'textarea[name="rubric[criteria][{cid}][description]"]', crit.descripcion)
            self._ajustar_niveles(cid, len(crit.niveles))
            lids = self.page.evaluate(JS_IDS_NIVELES, cid)
            for lid, nivel in zip(lids, crit.niveles):
                pref = f"rubric[criteria][{cid}][levels][{lid}]"
                self._poner(f'textarea[name="{pref}[definition]"]', nivel.definicion)
                self._poner(f'input[name="{pref}[score]"]', fmt_puntos(nivel.puntos))
            print(f"  · Criterio {i + 1}/{len(r.criterios)}: {crit.descripcion}")

        # Criterios sobrantes (p. ej. al sustituir una rúbrica que tenía más criterios)
        ids = self.page.evaluate(JS_IDS_CRITERIOS)
        for cid in reversed(ids[len(r.criterios):]):
            antes = len(self.page.evaluate(JS_IDS_CRITERIOS))
            self._clic(f'input[name="rubric[criteria][{cid}][delete]"]')
            self._confirmar_modal()
            self.page.wait_for_function(f"() => ({JS_IDS_CRITERIOS})().length < {antes}", timeout=10000)

        self._poner_opciones(r.opciones)

    def _ajustar_niveles(self, cid: str, necesarios: int):
        for _ in range(50):
            lids = self.page.evaluate(JS_IDS_NIVELES, cid)
            if len(lids) == necesarios:
                return
            if len(lids) < necesarios:
                self._clic(f'input[name="rubric[criteria][{cid}][levels][addlevel]"]')
            else:
                self._clic(f'input[name="rubric[criteria][{cid}][levels][{lids[-1]}][delete]"]')
                self._confirmar_modal()
            self.page.wait_for_function(
                f"(cid) => ({JS_IDS_NIVELES})(cid).length != {len(lids)}", arg=cid, timeout=10000)
        raise ErrorRubrica(f"No he podido ajustar el número de niveles del criterio {cid}.")

    def _confirmar_modal(self):
        # Algunas versiones usan un diálogo propio de Moodle en lugar de confirm() nativo.
        boton = self.page.locator(
            ".moodle-dialogue-confirm .btn-primary, .modal.show .modal-footer .btn-primary").first
        try:
            boton.click(timeout=3000)
            self.page.locator(".modal.show").first.wait_for(state="hidden", timeout=5000)
        except Exception:
            pass

    def _poner_descripcion(self, texto: str):
        html = "".join(f"<p>{escape(linea)}</p>" for linea in texto.split("\n") if linea.strip())
        self.page.evaluate(
            """(html) => {
                const ta = document.querySelector('textarea[name="description_editor[text]"]');
                if (ta) { ta.value = html; }
                if (window.tinymce && tinymce.get('id_description_editor')) {
                    tinymce.get('id_description_editor').setContent(html);
                }
                const atto = document.getElementById('id_description_editoreditable');
                if (atto) { atto.innerHTML = html; }
            }""", html)

    def _poner_opciones(self, opciones: dict[str, Any]):
        for clave, valor in opciones.items():
            nombre = f"rubric[options][{OPCIONES_MOODLE[clave]}]"
            loc = self.page.locator(f'[name="{nombre}"]:not([type="hidden"])').first
            if loc.count() == 0:
                print(f"  ! Opción «{clave}» no encontrada en esta versión de Moodle; se ignora.")
                continue
            tag = loc.evaluate("el => el.tagName.toLowerCase()")
            if tag == "select":
                loc.select_option(str(int(valor)) if isinstance(valor, bool) else str(valor))
            else:
                loc.set_checked(bool(valor))

    def guardar(self) -> None:
        if self.revisar:
            print("\n  → Revisa la rúbrica en el navegador. NO pulses guardar allí.")
            if not confirmar("    ¿Guardar ahora? [s/N] "):
                raise ErrorRubrica("Cancelado por el usuario: no se ha guardado nada; Moodle queda como estaba.")
        boton = "#id_saverubricdraft" if self.borrador else "#id_saverubric"
        self._clic(f'{boton}, input[name="{boton[4:]}"]')
        if "/grade/grading/form/rubric/edit.php" in self.page.url:
            errores = self.page.locator(".error:visible, .invalid-feedback:visible, .alert-danger:visible").all_inner_texts()
            detalle = "; ".join(t.strip() for t in errores if t.strip()) or "Moodle no ha aceptado el formulario."
            raise ErrorRubrica(f"No se ha guardado: {detalle}")


def importar(rubricas: list[Rubrica], args) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Falta Playwright. Instálalo con:\n  pip install playwright\n  python -m playwright install chromium")
        return 2

    fallos = 0
    with sync_playwright() as pw:
        lanzar = dict(user_data_dir=str(args.perfil), headless=False, viewport={"width": 1400, "height": 900})
        if args.navegador != "chromium":
            lanzar["channel"] = args.navegador
        ctx = pw.chromium.launch_persistent_context(**lanzar)
        # Moodle usa una cookie de sesión que el navegador descarta al cerrarse; la guardamos
        # en el perfil para no tener que iniciar sesión en cada ejecución mientras siga válida.
        fichero_sesion = args.perfil / "sesion_moodle.json"
        if fichero_sesion.exists() and not args.nueva_sesion:
            try:
                ctx.add_cookies(json.loads(fichero_sesion.read_text(encoding="utf-8")))
            except Exception:
                pass
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        imp = Importador(page, not args.sin_revisar, args.reemplazar, args.borrador)

        for r in rubricas:
            print("\n" + resumen(r))
            url = args.url or r.url
            url = normalizar_url_tarea(url, args.moodle) if url else pedir_url(r, args.moodle)
            base = raiz_moodle(url)
            try:
                contextid, titulo = imp.abrir_tarea(url)
                fichero_sesion.write_text(json.dumps(ctx.cookies()), encoding="utf-8")
                print(f"  · Tarea: {titulo}")
                areaid = imp.activar_rubrica(base, contextid)
                imp.rellenar(base, areaid, r)
                imp.guardar()
                print(f"  ✓ Rúbrica «{r.nombre}» guardada.")
                print("    Recuerda: Moodle escala la puntuación de la rúbrica a la calificación máxima de la tarea.")
            except ErrorRubrica as e:
                fallos += 1
                print(f"  ✗ {e}")
            except Exception as e:  # errores de Playwright: selector, tiempo de espera…
                fallos += 1
                captura = Path(f"error_{(r.origen.stem if r.origen else 'rubrica')}.png")
                try:
                    page.screenshot(path=str(captura), full_page=True)
                    print(f"  ✗ Error inesperado: {e}\n    Captura guardada en {captura.resolve()}")
                except Exception:
                    print(f"  ✗ Error inesperado: {e}")

        try:
            input("\nTerminado. Pulsa Intro para cerrar el navegador… ")
        except EOFError:
            pass
        ctx.close()
    return 1 if fallos else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Importa rúbricas en formato JSON a tareas de Moodle sin plugins.")
    ap.add_argument("ficheros", nargs="+", type=Path, help="Uno o varios ficheros JSON de rúbrica.")
    ap.add_argument("--url", help="URL de la tarea (…/mod/assign/view.php?id=NNN) o su id. Si no se da, se usa la del JSON o se pregunta.")
    ap.add_argument("--moodle", help="URL raíz de Moodle, necesaria si identificas la tarea solo por su id.")
    ap.add_argument("--sin-revisar", action="store_true",
                    help="No se detiene a pedir confirmación: guarda (y, con --reemplazar, sustituye) directamente. "
                         "Por defecto el script SIEMPRE pide confirmación antes de guardar o sustituir.")
    ap.add_argument("--reemplazar", action="store_true",
                    help="Si la tarea ya tiene rúbrica, permite sustituirla por la nueva (pidiendo confirmación, "
                         "salvo con --sin-revisar). Por defecto NUNCA se reemplaza una rúbrica existente.")
    ap.add_argument("--borrador", action="store_true", help="Guarda como borrador en lugar de dejarla lista para usar.")
    ap.add_argument("--nueva-sesion", action="store_true",
                    help="Ignora la sesión guardada y obliga a iniciar sesión de nuevo.")
    ap.add_argument("--solo-validar", action="store_true", help="Solo comprueba los JSON; no abre Moodle.")
    ap.add_argument("--navegador", default="chromium", choices=["chromium", "chrome", "msedge"],
                    help="Navegador a usar (por defecto, el Chromium de Playwright).")
    ap.add_argument("--perfil", type=Path, default=PERFIL_POR_DEFECTO,
                    help=f"Carpeta del perfil del navegador donde se guarda tu sesión (por defecto {PERFIL_POR_DEFECTO}).")
    args = ap.parse_args()

    if args.url and len(args.ficheros) > 1:
        ap.error("--url solo puede usarse con un único fichero JSON (o pon 'moodle.url_tarea' en cada JSON).")

    rubricas = []
    for f in args.ficheros:
        try:
            rubricas.append(cargar_rubrica(f))
        except (ErrorRubrica, OSError) as e:
            print(f"✗ {e}")
            return 1

    if args.solo_validar:
        for r in rubricas:
            print("✓ " + resumen(r))
        return 0
    return importar(rubricas, args)


if __name__ == "__main__":
    sys.exit(main())
