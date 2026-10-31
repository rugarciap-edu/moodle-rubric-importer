#!/usr/bin/env python3
"""Interfaz gráfica (tkinter) para importar_rubrica.py.

Acepta rúbricas .json o .xlsx (una) y lotes de rúbricas en JSON (array, {"rubricas": [...]}
o el maestro {"tareas": [...]}). Los Excel se convierten antes a un JSON temporal con
rub_xlsx2json.py. importar_rubrica.py se ejecuta como proceso hijo en modo --gui (protocolo
JSON por líneas) y sus preguntas (URL, confirmaciones, cierre del navegador) se contestan con
botones en esta ventana. En un lote se importa una
rúbrica tras otra, siempre con revisión, cada una con su URL de tarea.
"""
from __future__ import annotations

import copy
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

import gui_config
from generar_json import convertir
from gui_i18n import IDIOMAS, IDIOMA_POR_DEFECTO, set_idioma, t
from importar_rubrica import ErrorRubrica, cargar_rubrica, normalizar_url_tarea

AQUI = Path(__file__).resolve().parent
IMPORTADOR = AQUI / "importar_rubrica.py"
XLSX2JSON = AQUI / "rub_xlsx2json.py"
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ENV_UTF8 = {**os.environ, "PYTHONIOENCODING": "utf-8"}
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
NAVEGADORES = ["chromium", "chrome", "msedge"]
URL_PROYECTO = "https://github.com/rugarciap-edu/moodle-rubric-importer"
LICENCIA_GPL = """Copyright (C) Rubén García

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""


def python_consola() -> str:
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and (exe.with_name("python.exe")).exists():
        return str(exe.with_name("python.exe"))
    return str(exe)


def pts(p: Any) -> str:
    if isinstance(p, bool) or not isinstance(p, (int, float)):
        return "?"
    return str(int(p)) if float(p).is_integer() else str(p)


def avisos_estructura(datos: dict) -> list[str]:
    """Comprobaciones extra no cubiertas por importar_rubrica (escala del Excel)."""
    avisos = []
    esc = datos.get("escala")
    crit = datos.get("criterios")
    if isinstance(esc, dict) and isinstance(crit, list):
        n = esc.get("numero_niveles")
        nombres = esc.get("nombres_niveles")
        for i, c in enumerate(crit, 1):
            niv = c.get("niveles") if isinstance(c, dict) else None
            if not isinstance(niv, list):
                continue
            if isinstance(n, int) and len(niv) != n:
                avisos.append(t("aviso_niveles", i=i, n=len(niv), esc=n))
            elif isinstance(nombres, list):
                reales = [x.get("nombre") for x in niv if isinstance(x, dict)]
                if reales != nombres[:len(reales)]:
                    avisos.append(t("aviso_nombres", i=i))
    return avisos


def url_completa(texto: str) -> str:
    """Valida la URL completa de la tarea (la GUI no admite el id suelto)."""
    texto = texto.strip()
    if texto.isdigit():
        raise ErrorRubrica(t("err_url_id"))
    return normalizar_url_tarea(texto, None)


def url_de(datos: Any) -> str:
    moodle = datos.get("moodle") if isinstance(datos, dict) else None
    url = moodle.get("url_tarea") if isinstance(moodle, dict) else None
    return url.strip() if isinstance(url, str) else ""


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        prefs = gui_config.leer()
        self.idioma = tk.StringVar(value=set_idioma(prefs.get("IDIOMA", IDIOMA_POR_DEFECTO)))
        self.traducibles: list[tuple[Any, str, str]] = []
        self.title(t("app_titulo"))
        self.minsize(800, 680)
        self.proceso: subprocess.Popen | None = None
        self.tmpdir: Path | None = None
        self.cola: queue.Queue[str | None] = queue.Queue()
        self.trabajos: list[tuple[str, list[str]]] = []
        self.lote_detenido = False

        # Rúbricas cargadas: [{"etiqueta", "datos", "errores", "url": StringVar}]
        self.items: list[dict] = []
        self.es_lote = False
        self.marcos: list[tk.Frame] = []

        self.fichero = tk.StringVar()
        self.url = tk.StringVar()
        self.confirmar = tk.BooleanVar(value=gui_config.a_bool(prefs.get("CONFIRMAR"), True))
        self.borrador = tk.BooleanVar(value=gui_config.a_bool(prefs.get("BORRADOR"), False))
        self.nueva_sesion = tk.BooleanVar(value=False)
        self.solo_validar = tk.BooleanVar(value=False)
        navegador = prefs.get("NAVEGADOR", "chromium")
        self.navegador = tk.StringVar(value=navegador if navegador in NAVEGADORES else "chromium")

        self._construir_menu()
        self._construir()
        for v in (self.confirmar, self.borrador, self.navegador):
            v.trace_add("write", lambda *_a: self._guardar_prefs())
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.after(50, self._vaciar_cola)

    # ------------------------------------------- idioma y preferencias
    def _r(self, widget: Any, clave: str, opcion: str = "text") -> Any:
        """Registra un widget para retraducirlo al cambiar de idioma."""
        self.traducibles.append((widget, opcion, clave))
        widget.configure(**{opcion: t(clave)})
        return widget

    def _guardar_prefs(self) -> None:
        datos = {"IDIOMA": self.idioma.get(), "NAVEGADOR": self.navegador.get(),
                 "BORRADOR": str(self.borrador.get()).lower()}
        if not self.es_lote:  # en un lote la confirmación se fuerza y no es una preferencia
            datos["CONFIRMAR"] = str(self.confirmar.get()).lower()
        gui_config.guardar(datos)

    def _construir_menu(self) -> None:
        barra = tk.Menu(self)
        self.menu_archivo = tk.Menu(barra, tearoff=False)
        self.menu_archivo.add_command(command=self._cerrar)
        self.menu_config = tk.Menu(barra, tearoff=False)
        self.menu_idioma = tk.Menu(self.menu_config, tearoff=False)
        for cod in IDIOMAS:
            self.menu_idioma.add_radiobutton(variable=self.idioma, value=cod, command=self._cambiar_idioma)
        self.menu_config.add_cascade(menu=self.menu_idioma)
        self.menu_ayuda = tk.Menu(barra, tearoff=False)
        self.menu_ayuda.add_command(command=self._acerca_de)
        barra.add_cascade(menu=self.menu_archivo)
        barra.add_cascade(menu=self.menu_config)
        barra.add_cascade(menu=self.menu_ayuda)
        self.barra_menu = barra
        self.configure(menu=barra)
        self._traducir_menu()

    def _traducir_menu(self) -> None:
        self.barra_menu.entryconfigure(0, label=t("menu_archivo"))
        self.barra_menu.entryconfigure(1, label=t("menu_config"))
        self.barra_menu.entryconfigure(2, label=t("menu_ayuda"))
        self.menu_ayuda.entryconfigure(0, label=t("menu_acerca"))
        self.menu_archivo.entryconfigure(0, label=t("menu_salir"))
        self.menu_config.entryconfigure(0, label=t("menu_idioma"))
        for i, cod in enumerate(IDIOMAS):
            self.menu_idioma.entryconfigure(i, label=t(f"lang_{cod}"))

    def _acerca_de(self) -> None:
        d = tk.Toplevel(self)
        d.title(t("about_titulo"))
        d.transient(self)
        d.resizable(False, False)
        cuerpo = ttk.Frame(d, padding=16)
        cuerpo.pack(fill="both", expand=True)
        ttk.Label(cuerpo, text=t("app_titulo"), font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(cuerpo, text=t("about_autor")).pack(anchor="w", pady=(6, 0))
        fila = ttk.Frame(cuerpo)
        fila.pack(anchor="w", pady=(2, 8))
        ttk.Label(fila, text=t("about_proyecto")).pack(side="left")
        enlace = tk.Label(fila, text=URL_PROYECTO, fg="#0b57d0", cursor="hand2", font=("Segoe UI", 9, "underline"))
        enlace.pack(side="left", padx=6)
        enlace.bind("<Button-1>", lambda _e: webbrowser.open(URL_PROYECTO))
        ttk.Label(cuerpo, text=t("about_licencia")).pack(anchor="w")
        marco = ttk.Frame(cuerpo)
        marco.pack(fill="both", expand=True, pady=(2, 10))
        texto = tk.Text(marco, width=76, height=14, wrap="word", font=("Consolas", 9))
        barra = ttk.Scrollbar(marco, command=texto.yview)
        texto.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        texto.pack(side="left", fill="both", expand=True)
        texto.insert("1.0", LICENCIA_GPL)
        texto.configure(state="disabled")
        ttk.Button(cuerpo, text=t("btn_cerrar"), command=d.destroy).pack(anchor="e")
        d.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - d.winfo_reqwidth()) // 2
        d.geometry(f"+{max(x, 0)}+{self.winfo_rooty() + 40}")
        d.grab_set()
        d.focus_set()

    def _cambiar_idioma(self) -> None:
        set_idioma(self.idioma.get())
        self._guardar_prefs()
        self.title(t("app_titulo"))
        self._traducir_menu()
        for widget, opcion, clave in self.traducibles:
            widget.configure(**{opcion: t(clave)})
        self.nb.tab(0, text=t("tab_importar"))
        self.nb.tab(1, text=t("tab_vista"))
        if self._hay_cambios():
            self._repintar()
        else:
            self._actualizar_vista(True)
        self._actualizar_nav()

    # ---------------------------------------------------------------- UI
    def _construir(self) -> None:
        pad = {"padx": 8, "pady": 4}
        marco = self._r(ttk.LabelFrame(self), "grp_rubrica")
        marco.pack(fill="x", **pad)
        marco.columnconfigure(1, weight=1)
        self._r(ttk.Label(marco), "lbl_fichero").grid(row=0, column=0, sticky="w", **pad)
        entrada = ttk.Entry(marco, textvariable=self.fichero)
        entrada.grid(row=0, column=1, sticky="ew", **pad)
        entrada.bind("<Return>", lambda _e: self._actualizar_vista())
        entrada.bind("<FocusOut>", lambda _e: self._actualizar_vista())
        self._r(ttk.Button(marco, command=self._examinar), "btn_examinar").grid(row=0, column=2, **pad)
        self._r(ttk.Button(marco, command=self._recargar), "btn_recargar"
                ).grid(row=0, column=3, **pad)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=4)
        self.nb.bind("<<NotebookTabChanged>>",
                     lambda _e: self._actualizar_vista(True) if self.nb.index("current") == 1 else None)
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text=t("tab_importar"))
        self._construir_vista_previa()

        marco = self._r(ttk.LabelFrame(tab), "grp_tarea")
        marco.pack(fill="x", **pad)
        marco.columnconfigure(1, weight=1)
        self._r(ttk.Label(marco), "lbl_url").grid(row=0, column=0, sticky="w", **pad)
        self.ent_url = ttk.Entry(marco, textvariable=self.url)
        self.ent_url.grid(row=0, column=1, sticky="ew", **pad)
        self.btn_urls = self._r(ttk.Button(marco, command=self._popup_urls, state="disabled"), "btn_lote")
        self.btn_urls.grid(row=0, column=2, **pad)
        self.lbl_info_url = ttk.Label(marco, text=t("texto_url"), foreground="#555", wraplength=720)
        self.lbl_info_url.grid(row=1, column=0, columnspan=3, sticky="w", **pad)

        marco = self._r(ttk.LabelFrame(tab), "grp_opciones")
        marco.pack(fill="x", **pad)
        self.chk_confirmar = self._r(ttk.Checkbutton(marco, variable=self.confirmar), "chk_confirmar")
        self.chk_confirmar.pack(anchor="w", **pad)
        self._r(ttk.Checkbutton(marco, variable=self.borrador), "chk_borrador").pack(anchor="w", **pad)
        self._r(ttk.Checkbutton(marco, variable=self.nueva_sesion), "chk_sesion").pack(anchor="w", **pad)
        self._r(ttk.Checkbutton(marco, variable=self.solo_validar), "chk_validar").pack(anchor="w", **pad)
        fila = ttk.Frame(marco)
        fila.pack(anchor="w", **pad)
        self._r(ttk.Label(fila), "lbl_navegador").pack(side="left")
        ttk.Combobox(fila, textvariable=self.navegador, state="readonly", width=12,
                     values=NAVEGADORES).pack(side="left", padx=6)

        fila = ttk.Frame(tab)
        fila.pack(fill="x", **pad)
        self.btn_importar = self._r(ttk.Button(fila, command=self._importar), "btn_importar")
        self.btn_importar.pack(side="left")
        self.btn_parar = self._r(ttk.Button(fila, command=self._detener, state="disabled"), "btn_detener")
        self.btn_parar.pack(side="left", padx=6)
        self._r(ttk.Button(fila, command=self._limpiar_logs), "btn_limpiar").pack(side="left")
        self.lbl_spinner = ttk.Label(fila, text="", font=("Segoe UI Symbol", 11), foreground="#1f5fbf")
        self.lbl_spinner.pack(side="right", padx=4)
        self.spinner_activo = False
        self.spinner_i = 0

        marco = self._r(ttk.LabelFrame(tab), "grp_logs")
        marco.pack(fill="both", expand=True, **pad)
        self.salida = tk.Text(marco, height=12, wrap="word", state="disabled")
        barra = ttk.Scrollbar(marco, command=self.salida.yview)
        self.salida.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.salida.pack(fill="both", expand=True)

        self.dialogo: tk.Toplevel | None = None
        self.pregunta_activa: str | None = None

    # ------------------------------------------------------------ acciones
    def _examinar(self) -> None:
        ruta = filedialog.askopenfilename(
            title=t("dlg_examinar"),
            filetypes=[(t("ft_rubrica"), "*.json *.xlsx"), ("JSON", "*.json"), ("Excel", "*.xlsx")],
        )
        if ruta:
            self.fichero.set(ruta)
            self._actualizar_vista()

    # ------------------------------------------------------ vista previa
    def _construir_vista_previa(self) -> None:
        self.ultima_vista: str | None = None
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text=t("tab_vista"))
        self.lbl_estado = tk.Label(tab, anchor="w", justify="left", wraplength=740, padx=8, pady=6,
                                   text=t("texto_vacio"))
        self.lbl_estado.pack(fill="x")

        self.nav = ttk.Frame(tab)
        self._r(ttk.Button(self.nav, command=lambda: self._ir(-1)), "nav_anterior").pack(side="left", padx=4)
        self._r(ttk.Button(self.nav, command=lambda: self._ir(1)), "nav_siguiente").pack(side="left", padx=4)
        self.lbl_nav = ttk.Label(self.nav, text="")
        self.lbl_nav.pack(side="left", padx=10)

        self.cuerpo = ttk.Frame(tab)
        self.cuerpo.pack(fill="both", expand=True)
        self.lienzo = tk.Canvas(self.cuerpo, highlightthickness=0)
        self.vb = ttk.Scrollbar(self.cuerpo, orient="vertical", command=self.lienzo.yview)
        hb = ttk.Scrollbar(self.cuerpo, orient="horizontal", command=self.lienzo.xview)
        self.lienzo.configure(yscrollcommand=self._on_yscroll, xscrollcommand=hb.set)
        self.vb.pack(side="right", fill="y")
        hb.pack(side="bottom", fill="x")
        self.lienzo.pack(fill="both", expand=True)
        self.tabla = tk.Frame(self.lienzo)
        self.lienzo.create_window((0, 0), window=self.tabla, anchor="nw")
        self.tabla.bind("<Configure>", lambda _e: self.lienzo.configure(scrollregion=self.lienzo.bbox("all")))
        self.lienzo.bind("<Enter>", lambda _e: self.lienzo.bind_all("<MouseWheel>", self._rueda))
        self.lienzo.bind("<Leave>", lambda _e: self.lienzo.unbind_all("<MouseWheel>"))

    def _rueda(self, e: tk.Event) -> None:
        self.lienzo.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def _on_yscroll(self, a: str, b: str) -> None:
        self.vb.set(a, b)
        self._actualizar_nav()

    def _indice_actual(self) -> int:
        if not self.marcos:
            return 0
        top = self.lienzo.canvasy(0)
        actual = 0
        for i, m in enumerate(self.marcos):
            if m.winfo_y() <= top + 5:
                actual = i
        return actual

    def _actualizar_nav(self) -> None:
        if self.es_lote and self.marcos:
            i = self._indice_actual()
            self.lbl_nav.configure(text=t("nav_rubrica", i=i + 1, n=len(self.marcos), etiqueta=self.items[i]["etiqueta"]))

    def _ir(self, delta: int) -> None:
        if not self.marcos:
            return
        self.update_idletasks()
        i = min(max(self._indice_actual() + delta, 0), len(self.marcos) - 1)
        total = max(self.tabla.winfo_height(), 1)
        self.lienzo.yview_moveto(self.marcos[i].winfo_y() / total)

    # --- carga de datos (JSON individual, lote o Excel)
    @staticmethod
    def _etiqueta(clave: str) -> str:
        return t("tarea_n", n=clave[6:]) if clave.startswith("tarea:") else clave

    def _items_desde_json(self, datos: Any) -> tuple[list[tuple[str, Any]], bool]:
        """Devuelve [(clave, datos)]; la clave no depende del idioma (ver _etiqueta)."""
        if isinstance(datos, dict) and "tareas" in datos and isinstance(datos["tareas"], list):
            return [(f"tarea:{t_.get('numero', i)}", convertir(t_, "UD2"))
                    for i, t_ in enumerate(datos["tareas"], 1)], True
        if isinstance(datos, dict) and isinstance(datos.get("rubricas"), list):
            datos = datos["rubricas"]
        if isinstance(datos, list):
            return [(f"#{i}", d) for i, d in enumerate(datos, 1)], True
        return [("", datos)], False

    def _leer_fichero(self, ruta: Path) -> tuple[list[tuple[str, Any]], bool, str | None]:
        """Devuelve ([(etiqueta, datos)], es_lote, error de lectura)."""
        if ruta.suffix.lower() in (".xlsx", ".xlsm"):
            with tempfile.TemporaryDirectory(prefix="prev_") as tmp:
                destino = Path(tmp) / "r.json"
                r = subprocess.run(
                    [python_consola(), str(XLSX2JSON), str(ruta), str(destino)],
                    capture_output=True, text=True, encoding="utf-8", creationflags=SIN_VENTANA, env=ENV_UTF8,
                )
                if r.returncode != 0:
                    return [], False, (r.stderr or r.stdout).strip() or t("err_excel")
                return [("", json.loads(destino.read_text(encoding="utf-8")))], False, None
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as e:
            return [], False, t("err_json", l=e.lineno, c=e.colno, m=e.msg)
        except (OSError, UnicodeDecodeError) as e:
            return [], False, str(e)
        try:
            elementos, lote = self._items_desde_json(datos)
        except (KeyError, TypeError, ValueError) as e:
            return [], False, t("err_estructura", e=repr(e))
        return elementos, lote, None

    @staticmethod
    def _validar(datos: Any, nombre: str, original: Path | None) -> list[str]:
        errores: list[str] = []
        if not isinstance(datos, dict):
            return [t("err_objeto")]
        try:
            if original is not None:
                cargar_rubrica(original)
            else:
                with tempfile.TemporaryDirectory(prefix="val_") as tmp:
                    p = Path(tmp) / nombre
                    p.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
                    cargar_rubrica(p)
        except ErrorRubrica as e:
            errores.append(str(e))
        except (ValueError, TypeError) as e:
            errores.append(t("err_valor", e=e))
        return errores + avisos_estructura(datos)

    def _hay_cambios(self) -> bool:
        return any(it["datos"] != it["original"] for it in self.items)

    def _recargar(self) -> None:
        if self._hay_cambios() and not messagebox.askyesno(t("descartar_t"), t("descartar")):
            return
        self._actualizar_vista(True, True)

    def _actualizar_vista(self, forzar: bool = False, descartar: bool = False) -> None:
        texto = self.fichero.get().strip().strip('"')
        if not descartar and self._hay_cambios():
            if texto == self.ultima_vista:
                return
            if not messagebox.askyesno(t("descartar_t"), t("descartar")):
                self.fichero.set(self.ultima_vista or "")
                return
        if not forzar and texto == self.ultima_vista:
            return
        self.ultima_vista = texto
        previas = {it["clave"]: it["url"].get() for it in self.items}
        self._vaciar_tabla()
        self.items = []
        self.es_lote = False
        ruta = Path(texto)
        if not texto or not ruta.is_file():
            self.lbl_estado.configure(bg=self.cget("bg"), fg="black", text=t("texto_vacio"))
            self._aplicar_modo()
            return

        elementos, self.es_lote, error = self._leer_fichero(ruta)
        if error:
            self.lbl_estado.configure(bg="#fde2e2", fg="#8a1111", text=t("estado_no_valida", detalle=error))
            self._aplicar_modo()
            return

        for i, (clave, datos) in enumerate(elementos, 1):
            nombre = (re.sub(r"[^\w\-]+", "_", clave) if clave else ruta.stem) + ".json"
            original = ruta if (not self.es_lote and ruta.suffix.lower() == ".json") else None
            errores = self._validar(datos, nombre, original)
            url = tk.StringVar(value=previas.get(clave) or url_de(datos))
            self.items.append({"clave": clave, "etiqueta": self._etiqueta(clave) if clave else ruta.stem,
                               "datos": datos, "original": copy.deepcopy(datos), "nombre_fichero": nombre,
                               "errores": errores, "url": url})
        self._pintar()

    def _vaciar_tabla(self) -> None:
        for w in self.tabla.winfo_children():
            w.destroy()
        self.marcos = []
        self.nav.pack_forget()

    def _repintar(self) -> None:
        self._vaciar_tabla()
        self._pintar()

    def _pintar_estado(self) -> None:
        invalidas = [it for it in self.items if it["errores"]]
        if self.es_lote:
            n = len(self.items)
            if invalidas:
                self.lbl_estado.configure(
                    bg="#fde2e2", fg="#8a1111",
                    text=t("estado_lote_invalido", n=n, k=len(invalidas),
                           lista=", ".join(it["etiqueta"] for it in invalidas)))
            else:
                self.lbl_estado.configure(bg="#dff3e0", fg="#14571b", text=t("estado_lote_ok", n=n))
        elif invalidas:
            self.lbl_estado.configure(bg="#fde2e2", fg="#8a1111", text=t(
                "estado_no_valida", detalle="\n• ".join(invalidas[0]["errores"])))
        else:
            self.lbl_estado.configure(bg="#dff3e0", fg="#14571b", text=t("estado_ok"))

    def _texto_item(self, it: dict, i: int) -> tuple[str, bool]:
        ok = not it["errores"]
        return (f"{i}/{len(self.items)} · {it['etiqueta']}  —  "
                + (t("item_valida") if ok else t("item_no_valida", detalle="\n• ".join(it["errores"]))), ok)

    def _pintar(self) -> None:
        self._pintar_estado()
        if self.es_lote:
            self.nav.pack(fill="x", before=self.cuerpo)

        for i, it in enumerate(self.items, 1):
            marco = tk.Frame(self.tabla, bd=0)
            marco.pack(fill="x", anchor="nw", pady=(0, 18))
            self.marcos.append(marco)
            if self.es_lote:
                it["lbl_item"] = tk.Label(marco, anchor="w", justify="left", wraplength=740, padx=8, pady=4,
                                          font=("Segoe UI", 10, "bold"))
                it["lbl_item"].pack(fill="x")
                self._pintar_item(it, i)
            if isinstance(it["datos"], dict):
                self._dibujar(marco, it)
        self._aplicar_modo()
        self.after(100, self._actualizar_nav)

    def _pintar_item(self, it: dict, i: int) -> None:
        lbl = it.get("lbl_item")
        if lbl is not None:
            texto, ok = self._texto_item(it, i)
            lbl.configure(text=texto, bg="#dff3e0" if ok else "#fde2e2", fg="#14571b" if ok else "#8a1111")

    def _aplicar_modo(self) -> None:
        """Lote: una URL por rúbrica (popup) y revisión obligatoria."""
        if self.es_lote:
            self.ent_url.state(["disabled"])
            self.btn_urls.state(["!disabled"])
            self.confirmar.set(True)
            self.chk_confirmar.state(["disabled"])
            self._actualizar_info_urls()
        else:
            self.ent_url.state(["!disabled"])
            self.btn_urls.state(["disabled"])
            self.chk_confirmar.state(["!disabled"])
            self.lbl_info_url.configure(text=t("texto_url"))

    def _actualizar_info_urls(self) -> None:
        con_url = sum(1 for it in self.items if it["url"].get().strip())
        self.lbl_info_url.configure(text=t("info_lote", n=len(self.items), con_url=con_url))

    def _celda(self, parent: tk.Frame, fila: int, col: int, texto: str, ancho: int, **kw) -> None:
        opciones = dict(text=texto, wraplength=ancho, justify="left", anchor="nw", padx=6, pady=4,
                        bg="white", relief="solid", bd=1)
        opciones.update(kw)
        tk.Label(parent, **opciones).grid(row=fila, column=col, sticky="nsew")

    @staticmethod
    def _criterios(datos: dict) -> list[dict]:
        crit = datos.get("criterios") if isinstance(datos.get("criterios"), list) else []
        return [c for c in crit if isinstance(c, dict)]

    @staticmethod
    def _total_puntos(datos: dict) -> float:
        total = 0.0
        for c in App._criterios(datos):
            niv = c.get("niveles") if isinstance(c.get("niveles"), list) else []
            total += max([x["puntos"] for x in niv if isinstance(x, dict)
                          and isinstance(x.get("puntos"), (int, float)) and not isinstance(x.get("puntos"), bool)]
                         or [0])
        return total

    def _texto_cabecera(self, datos: dict) -> str:
        sub = t("max_puntos", p=pts(self._total_puntos(datos)))
        if datos.get("puntuacion_maxima") is not None:
            sub += t("declarada", p=pts(datos["puntuacion_maxima"]))
        sub += t("n_criterios", n=len(self._criterios(datos)))
        sub += "\n" + t("tarea_moodle", url=url_de(datos) or t("tarea_pendiente"))
        if datos.get("descripcion"):
            sub += f"\n{datos['descripcion']}"
        return sub

    def _cambio(self, it: dict) -> None:
        """Revalida la rúbrica tras una edición y refresca los textos de estado sin redibujar."""
        datos = it["datos"]
        if datos.get("puntuacion_maxima") is not None:
            datos["puntuacion_maxima"] = self._total_puntos(datos)
        it["errores"] = self._validar(datos, it["nombre_fichero"], None)
        it["lbl_cab"].configure(text=self._texto_cabecera(datos))
        self._pintar_item(it, next(i for i, x in enumerate(self.items, 1) if x is it))
        self._pintar_estado()

    @staticmethod
    def _parsear_puntos(texto: str) -> Any:
        try:
            valor = float(texto.strip().replace(",", "."))
        except ValueError:
            return texto
        return int(valor) if valor.is_integer() else valor

    def _campo_texto(self, parent: tk.Frame, fila: int, col: int, ancho: int, valor: str, guardar: Any,
                     **kw: Any) -> None:
        """Celda de texto editable; guardar(nuevo) se llama solo si el contenido cambia."""
        chars = max(10, ancho // 7)
        lineas = sum(max(1, -(-len(p) // chars)) for p in (valor or " ").split("\n"))
        w = tk.Text(parent, width=chars, height=max(2, lineas), wrap="word", padx=6, pady=4,
                    relief="solid", bd=1, undo=True, font=kw.pop("font", ("Segoe UI", 9)), **kw)
        w.insert("1.0", valor)
        w.grid(row=fila, column=col, sticky="nsew")

        def confirmar(_e: Any = None) -> None:
            nuevo = w.get("1.0", "end-1c")
            if nuevo != valor_actual[0]:
                valor_actual[0] = nuevo
                guardar(nuevo)
        valor_actual = [valor]
        w.bind("<KeyRelease>", confirmar)
        w.bind("<FocusOut>", confirmar)

    def _dibujar(self, parent: tk.Frame, it: dict) -> None:
        datos = it["datos"]
        cab = ttk.Frame(parent)
        cab.pack(fill="x", anchor="nw", pady=(0, 4))
        ttk.Label(cab, text=t("lbl_nombre")).pack(side="left", padx=(0, 6))
        var_nombre = tk.StringVar(value=str(datos.get("nombre") or ""))
        ent = ttk.Entry(cab, textvariable=var_nombre)
        ent.pack(side="left", fill="x", expand=True)

        def nombre_cambiado(*_a: Any) -> None:
            if var_nombre.get() != str(datos.get("nombre") or ""):
                datos["nombre"] = var_nombre.get()
                self._cambio(it)
        var_nombre.trace_add("write", nombre_cambiado)

        tabla = tk.Frame(parent)
        tabla.pack(fill="x", anchor="nw")
        crit = self._criterios(datos)
        niveles = [c.get("niveles") if isinstance(c.get("niveles"), list) else [] for c in crit]
        n_cols = max([len(n) for n in niveles] + [1])
        ancho = max(140, min(260, 760 // n_cols))

        it["lbl_cab"] = tk.Label(tabla, text=self._texto_cabecera(datos), wraplength=ancho * (n_cols + 1),
                                 justify="left", anchor="nw", padx=6, pady=4, bg="#e8eef7", relief="solid", bd=1,
                                 font=("Segoe UI", 10))
        it["lbl_cab"].grid(row=0, column=0, columnspan=n_cols + 1, sticky="nsew")

        negrita = ("Segoe UI", 9, "bold")
        self._celda(tabla, 1, 0, t("col_criterio"), ancho, bg="#f0f0f0", font=negrita)
        for j in range(n_cols):
            nombre = ""
            for n in niveles:
                if j < len(n) and isinstance(n[j], dict) and n[j].get("nombre"):
                    nombre = str(n[j]["nombre"])
                    break
            self._celda(tabla, 1, j + 1, nombre or t("nivel_n", n=j + 1), ancho, bg="#f0f0f0", font=negrita)

        def asignar(destino: dict, clave: str) -> Any:
            def f(valor: Any) -> None:
                destino[clave] = valor
                self._cambio(it)
            return f

        for i, (c, niv) in enumerate(zip(crit, niveles), start=2):
            self._campo_texto(tabla, i, 0, ancho, str(c.get("descripcion") or ""), asignar(c, "descripcion"),
                              font=negrita)
            for j in range(n_cols):
                if j < len(niv) and isinstance(niv[j], dict):
                    x = niv[j]
                    celda = tk.Frame(tabla, bg="white", relief="solid", bd=1)
                    celda.grid(row=i, column=j + 1, sticky="nsew")
                    celda.columnconfigure(0, weight=1)
                    self._campo_texto(celda, 0, 0, ancho, str(x.get("definicion") or ""), asignar(x, "definicion"))
                    fila_p = tk.Frame(celda, bg="white")
                    fila_p.grid(row=1, column=0, sticky="w", padx=4, pady=2)
                    tk.Label(fila_p, text=t("lbl_puntos"), bg="white").pack(side="left")
                    var_p = tk.StringVar(value="" if x.get("puntos") is None else pts(x["puntos"]))
                    guardar_p = asignar(x, "puntos")

                    def puntos_cambiados(*_a: Any, x=x, var_p=var_p, guardar_p=guardar_p) -> None:
                        nuevo = self._parsear_puntos(var_p.get())
                        if nuevo != x.get("puntos"):
                            guardar_p(nuevo)
                    var_p.trace_add("write", puntos_cambiados)
                    ttk.Entry(fila_p, textvariable=var_p, width=7).pack(side="left", padx=4)
                else:
                    self._celda(tabla, i, j + 1, "", ancho, bg="#f6f6f6")

    # --- URLs del lote
    def _popup_urls(self) -> None:
        if not self.es_lote or not self.items:
            return
        top = tk.Toplevel(self)
        top.title(t("popup_titulo"))
        top.transient(self)
        top.geometry(f"820x{min(150 + 38 * len(self.items), 600)}")
        top.grab_set()

        ttk.Label(top, wraplength=780, foreground="#555", text=t("popup_desc")).pack(fill="x", padx=10, pady=8)

        cuerpo = ttk.Frame(top)
        cuerpo.pack(fill="both", expand=True, padx=10)
        lienzo = tk.Canvas(cuerpo, highlightthickness=0)
        barra = ttk.Scrollbar(cuerpo, orient="vertical", command=lienzo.yview)
        lienzo.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        lienzo.pack(side="left", fill="both", expand=True)
        filas = ttk.Frame(lienzo)
        lienzo.create_window((0, 0), window=filas, anchor="nw")
        filas.bind("<Configure>", lambda _e: lienzo.configure(scrollregion=lienzo.bbox("all")))
        lienzo.bind("<Enter>", lambda _e: lienzo.bind_all(
            "<MouseWheel>", lambda e: lienzo.yview_scroll(-1 if e.delta > 0 else 1, "units")))
        lienzo.bind("<Leave>", lambda _e: lienzo.unbind_all("<MouseWheel>"))
        filas.columnconfigure(1, weight=1)

        variables = []
        for i, it in enumerate(self.items):
            nombre = it["datos"].get("nombre", "") if isinstance(it["datos"], dict) else ""
            ttk.Label(filas, text=f"{i + 1}. {it['etiqueta']}", width=14).grid(row=i, column=0, sticky="nw", pady=3)
            v = tk.StringVar(value=it["url"].get())
            variables.append(v)
            celda = ttk.Frame(filas)
            celda.grid(row=i, column=1, sticky="ew", pady=3)
            celda.columnconfigure(0, weight=1)
            ttk.Label(celda, text=nombre + ("  " + t("item_no_valida", detalle="").split("\n")[0] if it["errores"] else ""),
                      foreground="#8a1111" if it["errores"] else "#555", wraplength=620).grid(row=0, column=0, sticky="w")
            ttk.Entry(celda, textvariable=v, width=80).grid(row=1, column=0, sticky="ew")

        def aceptar() -> None:
            for it, v in zip(self.items, variables):
                texto = v.get().strip()
                if not texto:
                    continue
                try:
                    url_completa(texto)
                except ErrorRubrica as e:
                    messagebox.showerror(t("err_url_t"), f"{it['etiqueta']}: {e}", parent=top)
                    return
            for it, v in zip(self.items, variables):
                it["url"].set(v.get().strip())
            self._actualizar_info_urls()
            lienzo.unbind_all("<MouseWheel>")
            top.destroy()

        botones = ttk.Frame(top)
        botones.pack(fill="x", padx=10, pady=8)
        ttk.Button(botones, text=t("popup_aceptar"), command=aceptar).pack(side="right")
        ttk.Button(botones, text=t("popup_cancelar"),
                   command=lambda: (lienzo.unbind_all("<MouseWheel>"), top.destroy())).pack(side="right", padx=6)

    # ------------------------------------------------------- importación
    def _escribir(self, texto: str) -> None:
        self.salida.configure(state="normal")
        self.salida.insert("end", texto)
        self.salida.see("end")
        self.salida.configure(state="disabled")

    def _limpiar_logs(self) -> None:
        self.salida.configure(state="normal")
        self.salida.delete("1.0", "end")
        self.salida.configure(state="disabled")

    def _estado_ejecucion(self, ejecutando: bool) -> None:
        self.btn_importar.state(["disabled" if ejecutando else "!disabled"])
        self.btn_parar.state(["!disabled" if ejecutando else "disabled"])
        if ejecutando:
            if not self.spinner_activo:
                self.spinner_activo = True
                self._girar()
        else:
            self.spinner_activo = False
            self.lbl_spinner.configure(text="")
            self._ocultar_panel()

    def _girar(self) -> None:
        if not self.spinner_activo:
            return
        self.spinner_i = (self.spinner_i + 1) % len(SPINNER)
        self.lbl_spinner.configure(text=f"{SPINNER[self.spinner_i]}  {t('spinner')}")
        self.after(90, self._girar)

    def _preparar_json(self, ruta: Path) -> Path | None:
        if self.items and self._hay_cambios():
            self.tmpdir = Path(tempfile.mkdtemp(prefix="rubrica_"))
            destino = self.tmpdir / (ruta.stem + ".json")
            destino.write_text(json.dumps(self.items[0]["datos"], ensure_ascii=False, indent=2), encoding="utf-8")
            return destino
        if ruta.suffix.lower() == ".json":
            return ruta
        if ruta.suffix.lower() not in (".xlsx", ".xlsm"):
            messagebox.showerror(t("err_formato_t"), t("err_formato"))
            return None
        self.tmpdir = Path(tempfile.mkdtemp(prefix="rubrica_"))
        destino = self.tmpdir / (ruta.stem + ".json")
        r = subprocess.run(
            [python_consola(), str(XLSX2JSON), str(ruta), str(destino)],
            capture_output=True, text=True, encoding="utf-8", creationflags=SIN_VENTANA, env=ENV_UTF8,
        )
        self._escribir(f"{t('conv_excel')}\n{r.stdout}{r.stderr}")
        if r.returncode != 0:
            self._limpiar_tmp()
            return None
        return destino

    def _opciones_comunes(self) -> list[str]:
        cmd: list[str] = []
        if self.borrador.get():
            cmd.append("--borrador")
        return cmd

    def _importar(self) -> None:
        ruta = Path(self.fichero.get().strip().strip('"'))
        if not ruta.is_file():
            messagebox.showerror(t("err_falta_t"), t("err_falta"))
            return
        self._actualizar_vista()
        if self.es_lote:
            self._importar_lote()
            return

        self.salida.configure(state="normal")
        self.salida.delete("1.0", "end")
        self.salida.configure(state="disabled")
        json_ruta = self._preparar_json(ruta)
        if json_ruta is None:
            return

        cmd = [python_consola(), "-u", str(IMPORTADOR), str(json_ruta)]
        if self.url.get().strip():
            try:
                cmd += ["--url", url_completa(self.url.get())]
            except ErrorRubrica as e:
                messagebox.showerror(t("err_url_t"), str(e))
                self._limpiar_tmp()
                return
        cmd += self._opciones_comunes()
        if not self.confirmar.get():
            cmd.append("--sin-revisar")
        if self.nueva_sesion.get():
            cmd.append("--nueva-sesion")
        if self.solo_validar.get():
            cmd.append("--solo-validar")
        cmd += ["--navegador", self.navegador.get()]
        self.trabajos = [("", cmd)]
        self.lote_detenido = False
        self._lanzar_siguiente()

    def _construir_trabajos_lote(self) -> list[tuple[str, list[str]]] | None:
        """Escribe cada rúbrica en un JSON temporal y devuelve (etiqueta, comando) por rúbrica."""
        invalidas = [it["etiqueta"] for it in self.items if it["errores"]]
        if invalidas:
            messagebox.showerror(t("err_lote_t"), t("err_lote") + "\n• " + "\n• ".join(invalidas))
            return None
        self.tmpdir = Path(tempfile.mkdtemp(prefix="lote_"))
        ficheros = []
        for i, it in enumerate(self.items, 1):
            f = self.tmpdir / f"{i:02d}_{re.sub(r'[^\w\-]+', '_', it['etiqueta'])}.json"
            f.write_text(json.dumps(it["datos"], ensure_ascii=False, indent=2), encoding="utf-8")
            ficheros.append(f)
        base = [python_consola(), "-u", str(IMPORTADOR)]

        if self.solo_validar.get():
            return [("lote", base + [str(f) for f in ficheros] + ["--solo-validar"])]

        trabajos = []
        for it, f in zip(self.items, ficheros):
            texto = it["url"].get().strip()
            if not texto:
                continue
            try:
                url = url_completa(texto)
            except ErrorRubrica as e:
                messagebox.showerror(t("err_url_t"), f"{it['etiqueta']}: {e}")
                self._limpiar_tmp()
                return None
            # Sin --sin-revisar: en un lote la revisión es siempre obligatoria
            cmd = base + [str(f), "--url", url] + self._opciones_comunes() + ["--navegador", self.navegador.get()]
            if self.nueva_sesion.get() and not trabajos:
                cmd.append("--nueva-sesion")
            trabajos.append((it["etiqueta"], cmd))
        return trabajos

    def _importar_lote(self) -> None:
        sin_url = [it["etiqueta"] for it in self.items if not it["url"].get().strip()]
        if not self.solo_validar.get():
            if len(sin_url) == len(self.items):
                messagebox.showinfo(t("faltan_t"), t("faltan"))
                self._popup_urls()
                return
            if sin_url and not messagebox.askyesno(
                    t("sin_tarea_t"),
                    t("sin_tarea", n=len(sin_url)) + "\n• " + "\n• ".join(sin_url) + "\n\n" + t("sin_tarea_fin")):
                return
        self.salida.configure(state="normal")
        self.salida.delete("1.0", "end")
        self.salida.configure(state="disabled")
        trabajos = self._construir_trabajos_lote()
        if not trabajos:
            return
        self.trabajos = trabajos
        self.lote_detenido = False
        self._lanzar_siguiente()

    def _lanzar_siguiente(self) -> None:
        etiqueta, cmd = self.trabajos.pop(0)
        if self.es_lote and etiqueta != "lote":
            self._escribir("\n" + t("lote_cab", etiqueta=etiqueta, n=len(self.trabajos)) + "\n")
        self._escribir("$ " + " ".join(cmd) + "\n\n")
        cmd = cmd + ["--gui"]
        try:
            self.proceso = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=str(AQUI), creationflags=SIN_VENTANA, env=ENV_UTF8,
            )
        except OSError as e:
            messagebox.showerror(t("no_ejecuta_t"), str(e))
            self.trabajos = []
            self._estado_ejecucion(False)
            self._limpiar_tmp()
            return
        self._estado_ejecucion(True)
        threading.Thread(target=self._leer, args=(self.proceso,), daemon=True).start()

    def _leer(self, proc: subprocess.Popen) -> None:
        # El protocolo es una línea por mensaje; stderr va mezclado y se muestra tal cual.
        for linea in proc.stdout:
            self.cola.put(linea.decode("utf-8", "replace"))
        proc.wait()
        self.cola.put(None)

    # Textos de la GUI para cada código del protocolo de importar_rubrica.py --gui
    def _texto_mensaje(self, m: dict) -> str | None:
        c = m.get("codigo")
        d = m.get("detalle", "")
        if c == "resumen":
            cab = "✓ " if m.get("validado") else "\n"
            lineas = [cab + t("p_resumen", nombre=m["nombre"], n=len(m["criterios"]), max=pts(m["maximo"]))]
            for i, k in enumerate(m["criterios"], 1):
                lineas.append(f"  {i}. {k['descripcion']}  [{' / '.join(pts(p) for p in k['puntos'])}]")
            return "\n".join(lineas)
        return {
            "falta_playwright": lambda: t("p_falta_pw"),
            "error_validacion": lambda: f"✗ {d}",
            "url_invalida": lambda: f"  ✗ {d}",
            "login_requerido": lambda: t("p_login"),
            "tarea": lambda: t("p_tarea", titulo=m.get("titulo", "")),
            "rubrica_existente": lambda: t("p_existente"),
            "sobrescribira": lambda: t("p_sobrescribe"),
            "criterio": lambda: t("p_criterio", i=m.get("indice"), n=m.get("total"),
                                  descripcion=m.get("descripcion", "")),
            "opcion_ignorada": lambda: t("p_opcion", opcion=m.get("opcion")),
            "rubrica_guardada": lambda: t("p_guardada", nombre=m.get("nombre")),
            "error": lambda: f"  ✗ {d}",
            "error_inesperado": lambda: t("p_inesperado", d=d)
                                + (t("p_captura", c=m["captura"]) if m.get("captura") else ""),
        }.get(c, lambda: f"[{c}]")()

    def _procesar_linea(self, linea: str) -> None:
        if not linea.startswith("@@"):
            self._escribir(linea)
            return
        try:
            m = json.loads(linea[2:])
        except ValueError:
            self._escribir(linea)
            return
        if m.get("tipo") == "pregunta":
            self._mostrar_pregunta(m)
            return
        self._ocultar_panel()
        texto = self._texto_mensaje(m)
        if texto:
            self._escribir(texto + "\n")
        c = m.get("codigo")
        if c == "login_requerido":
            self._mostrar_espera(t("login_cab"), t("login_txt"))
        elif c in ("error", "error_inesperado", "error_validacion", "falta_playwright", "url_invalida"):
            messagebox.showerror(t("t_imp"), (texto or "").strip())
        elif c == "rubrica_guardada":
            messagebox.showinfo(t("t_imp"), t("ok_guardada", nombre=m.get("nombre")))

    # ------------------------------------------------- panel de respuesta
    def _ocultar_panel(self) -> None:
        self.pregunta_activa = None
        self._cerrar_aviso_nativo()
        if self.dialogo is not None:
            try:
                self.dialogo.grab_release()
                self.dialogo.destroy()
            except tk.TclError:
                pass
            self.dialogo = None

    def _abrir_dialogo(self, titulo: str, cabecera: str, texto: str, cierre: Any) -> tk.Toplevel:
        """Ventana modal tipo asistente, siempre por encima del navegador."""
        self._ocultar_panel()
        d = tk.Toplevel(self)
        d.title(titulo)
        d.transient(self)
        d.resizable(False, False)
        d.attributes("-topmost", True)
        d.protocol("WM_DELETE_WINDOW", cierre)
        cuerpo = tk.Frame(d, bg="white", padx=20, pady=22)
        cuerpo.pack(fill="both", expand=True)
        d.cuerpo = cuerpo
        tk.Label(cuerpo, bitmap="info", bg="white").pack(side="left", anchor="n", padx=(0, 16))
        tk.Label(cuerpo, text=f"{cabecera}\n\n{texto}", justify="left", wraplength=420, bg="white",
                 font=("Segoe UI", 10)).pack(side="left", anchor="n")
        d.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - d.winfo_reqwidth()) // 2
        y = self.winfo_rooty() + 80
        d.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.dialogo = d
        self.bell()
        return d

    @staticmethod
    def _hacer_modal(d: tk.Toplevel, foco: Any = None) -> None:
        def _go() -> None:
            try:
                d.lift()
                d.grab_set()
                (foco or d).focus_force()
            except tk.TclError:
                pass  # el diálogo ya se cerró
        d.after(150, _go)

    def _mostrar_pregunta(self, m: dict) -> None:
        """Preguntas con los cuadros de diálogo nativos del sistema (con icono)."""
        c = m.get("codigo")
        self._ocultar_panel()
        self.pregunta_activa = c
        # La ventana pasa al frente (el navegador puede estar encima) y el cuadro se abre sobre ella
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.update()
        self.attributes("-topmost", False)
        titulo = t("t_imp")
        if c == "url":
            texto = self._preguntar_url(m.get("rubrica", ""))
            if texto is None:
                self._detener()
                return
            self._responder(texto)
            return
        if c == "confirmar_sustitucion":
            valor = messagebox.askyesno(titulo, t("q_sustituir"), icon="warning", parent=self)
        elif c == "confirmar_guardado":
            valor = messagebox.askyesno(titulo, t("q_guardar"), icon="question", parent=self)
        elif c == "cerrar_navegador":
            messagebox.showinfo(titulo, t("q_fin"), parent=self)
            valor = True
        else:
            valor = messagebox.askyesno(titulo, str(c), parent=self)
        self._responder(bool(valor))

    def _preguntar_url(self, rubrica: str) -> str | None:
        return simpledialog.askstring(t("q_url_t"), t("q_url", rubrica=rubrica), parent=self)

    def _mostrar_espera(self, cabecera: str, texto: str) -> None:
        """Aviso sin botones de acción; se cierra solo cuando el script avanza."""
        if os.name != "nt":
            self._abrir_dialogo(t("t_imp"), cabecera, texto, lambda: None)
            return
        self._ocultar_panel()
        import ctypes
        self.aviso_titulo = cabecera
        # MB_OK | MB_ICONINFORMATION | MB_SYSTEMMODAL | MB_SETFOREGROUND | MB_TOPMOST
        estilo = 0x0 | 0x40 | 0x1000 | 0x10000 | 0x40000
        threading.Thread(target=lambda: ctypes.windll.user32.MessageBoxW(0, texto, cabecera, estilo),
                         daemon=True).start()

    def _cerrar_aviso_nativo(self) -> None:
        titulo = getattr(self, "aviso_titulo", None)
        if not titulo:
            return
        self.aviso_titulo = None
        import ctypes
        hwnd = ctypes.windll.user32.FindWindowW("#32770", titulo)
        if hwnd:
            ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE

    def _vaciar_cola(self) -> None:
        try:
            while True:
                item = self.cola.get_nowait()
                if item is None:
                    codigo = self.proceso.returncode if self.proceso else "?"
                    self._escribir("\n" + t("proc_fin", c=codigo) + "\n")
                    self.proceso = None
                    if self.trabajos and not self.lote_detenido:
                        self._lanzar_siguiente()
                    else:
                        if self.trabajos:
                            self._escribir(t("lote_detenido", n=len(self.trabajos)) + "\n")
                        elif self.es_lote:
                            self._escribir(t("lote_fin") + "\n")
                        self.trabajos = []
                        self._estado_ejecucion(False)
                        self._limpiar_tmp()
                        if not self.lote_detenido and self._hay_cambios():
                            self.after(100, self._ofrecer_guardar)
                    self._procesar_linea(item)
        except queue.Empty:
            pass
        self.after(50, self._vaciar_cola)

    def _responder(self, valor: Any) -> None:
        if not self.proceso or self.proceso.stdin is None:
            return
        try:
            self.proceso.stdin.write((json.dumps({"respuesta": valor}) + "\n").encode("utf-8"))
            self.proceso.stdin.flush()
        except OSError:
            return
        if isinstance(valor, bool):
            etiqueta = t("resp_si") if valor else t("resp_no")
        else:
            etiqueta = str(valor)
        if self.pregunta_activa != "cerrar_navegador":
            self._escribir(f"  » {etiqueta}\n")
        self._ocultar_panel()

    def _detener(self) -> None:
        self.lote_detenido = True
        if self.proceso:
            self.proceso.terminate()

    def _limpiar_tmp(self) -> None:
        if self.tmpdir:
            shutil.rmtree(self.tmpdir, ignore_errors=True)
            self.tmpdir = None

    # --- guardar los cambios hechos en la vista previa
    def _contenido_para_guardar(self, ruta: Path) -> tuple[Any, bool]:
        """Devuelve (contenido JSON, ¿se puede sobrescribir el original sin perder su estructura?)."""
        datos = [it["datos"] for it in self.items]
        if not self.es_lote:
            return datos[0], ruta.suffix.lower() == ".json"
        if ruta.suffix.lower() != ".json":
            return datos, False
        try:
            orig = json.loads(ruta.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return datos, False
        if isinstance(orig, dict) and isinstance(orig.get("rubricas"), list):
            return {**orig, "rubricas": datos}, True
        if isinstance(orig, list):
            return datos, True
        return datos, False  # formato maestro {"tareas": ...}: no se puede reconstruir

    def _ofrecer_guardar(self) -> None:
        ruta = Path(self.fichero.get().strip().strip('"'))
        if not ruta.is_file() or not self._hay_cambios():
            return
        contenido, puede_sobrescribir = self._contenido_para_guardar(ruta)
        eleccion = self._preguntar_guardado(puede_sobrescribir)
        destino = None
        if eleccion == "sobrescribir":
            destino = ruta
        elif eleccion == "como":
            elegido = filedialog.asksaveasfilename(
                parent=self, title=t("guardar_como_t"), defaultextension=".json",
                initialdir=str(ruta.parent), initialfile=ruta.stem + ".json",
                filetypes=[("JSON", "*.json")])
            destino = Path(elegido) if elegido else None
        if destino is None:
            return
        try:
            destino.write_text(json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            messagebox.showerror(t("guardar_t"), str(e))
            return
        messagebox.showinfo(t("guardar_t"), t("guardado", ruta=str(destino)))
        self.fichero.set(str(destino))
        self._actualizar_vista(True, True)

    def _preguntar_guardado(self, puede_sobrescribir: bool) -> str | None:
        d = tk.Toplevel(self)
        d.title(t("guardar_t"))
        d.transient(self)
        d.resizable(False, False)
        resultado: list[str | None] = [None]
        ttk.Label(d, text=t("guardar_txt") + ("" if puede_sobrescribir else "\n" + t("guardar_no_sobrescribir")),
                  wraplength=420, justify="left").pack(padx=16, pady=14)
        botones = ttk.Frame(d)
        botones.pack(padx=16, pady=(0, 14))

        def elegir(valor: str | None) -> None:
            resultado[0] = valor
            d.destroy()
        b = ttk.Button(botones, text=t("btn_sobrescribir"), command=lambda: elegir("sobrescribir"))
        b.pack(side="left", padx=4)
        if not puede_sobrescribir:
            b.state(["disabled"])
        ttk.Button(botones, text=t("btn_guardar_como"), command=lambda: elegir("como")).pack(side="left", padx=4)
        ttk.Button(botones, text=t("btn_nada"), command=lambda: elegir(None)).pack(side="left", padx=4)
        d.protocol("WM_DELETE_WINDOW", lambda: elegir(None))
        d.grab_set()
        self.wait_window(d)
        return resultado[0]

    def _cerrar(self) -> None:
        if self.proceso:
            if not messagebox.askyesno(t("salir_t"), t("salir")):
                return
            self.lote_detenido = True
            self.proceso.terminate()
        self._limpiar_tmp()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
