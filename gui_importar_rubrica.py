#!/usr/bin/env python3
"""Interfaz gráfica (tkinter) para importar_rubrica.py.

Acepta rúbricas .json o .xlsx (una) y lotes de rúbricas en JSON (array, {"rubricas": [...]}
o el maestro {"tareas": [...]}). Los Excel se convierten antes a un JSON temporal con
rub_xlsx2json.py. importar_rubrica.py se ejecuta como proceso hijo y sus preguntas
(confirmaciones, Intro final) se contestan desde esta ventana. En un lote se importa una
rúbrica tras otra, siempre con revisión, cada una con su URL de tarea.
"""
from __future__ import annotations

import codecs
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
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from generar_json import convertir
from importar_rubrica import ErrorRubrica, cargar_rubrica, normalizar_url_tarea

AQUI = Path(__file__).resolve().parent
IMPORTADOR = AQUI / "importar_rubrica.py"
XLSX2JSON = AQUI / "rub_xlsx2json.py"
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ENV_UTF8 = {**os.environ, "PYTHONIOENCODING": "utf-8"}
TEXTO_URL = ("URL completa de la tarea (…/mod/assign/view.php?id=NNN). "
             "Vacío = se usa la del fichero o el script la pregunta.")
TEXTO_VACIO = "Selecciona un fichero de rúbrica para previsualizarlo."


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
                avisos.append(f"Criterio {i}: tiene {len(niv)} niveles y la escala indica {n}.")
            elif isinstance(nombres, list):
                reales = [x.get("nombre") for x in niv if isinstance(x, dict)]
                if reales != nombres[:len(reales)]:
                    avisos.append(f"Criterio {i}: los nombres de nivel no coinciden con la escala.")
    return avisos


def url_completa(texto: str) -> str:
    """Valida la URL completa de la tarea (la GUI no admite el id suelto)."""
    texto = texto.strip()
    if texto.isdigit():
        raise ErrorRubrica("Indica la URL completa de la tarea (…/mod/assign/view.php?id=NNN), no solo el id.")
    return normalizar_url_tarea(texto, None)


def url_de(datos: Any) -> str:
    moodle = datos.get("moodle") if isinstance(datos, dict) else None
    url = moodle.get("url_tarea") if isinstance(moodle, dict) else None
    return url.strip() if isinstance(url, str) else ""


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Importar rúbrica en Moodle")
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
        self.confirmar = tk.BooleanVar(value=True)
        self.reemplazar = tk.BooleanVar(value=False)
        self.borrador = tk.BooleanVar(value=False)
        self.nueva_sesion = tk.BooleanVar(value=False)
        self.solo_validar = tk.BooleanVar(value=False)
        self.navegador = tk.StringVar(value="chromium")

        self._construir()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.after(50, self._vaciar_cola)

    # ---------------------------------------------------------------- UI
    def _construir(self) -> None:
        pad = {"padx": 8, "pady": 4}
        marco = ttk.LabelFrame(self, text="Rúbrica")
        marco.pack(fill="x", **pad)
        marco.columnconfigure(1, weight=1)
        ttk.Label(marco, text="Fichero (.json / .xlsx):").grid(row=0, column=0, sticky="w", **pad)
        entrada = ttk.Entry(marco, textvariable=self.fichero)
        entrada.grid(row=0, column=1, sticky="ew", **pad)
        entrada.bind("<Return>", lambda _e: self._actualizar_vista())
        entrada.bind("<FocusOut>", lambda _e: self._actualizar_vista())
        ttk.Button(marco, text="Examinar…", command=self._examinar).grid(row=0, column=2, **pad)
        ttk.Button(marco, text="Recargar", command=lambda: self._actualizar_vista(True)).grid(row=0, column=3, **pad)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=4)
        self.nb.bind("<<NotebookTabChanged>>",
                     lambda _e: self._actualizar_vista(True) if self.nb.index("current") == 1 else None)
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Importar")
        self._construir_vista_previa()

        marco = ttk.LabelFrame(tab, text="Tarea de Moodle")
        marco.pack(fill="x", **pad)
        marco.columnconfigure(1, weight=1)
        ttk.Label(marco, text="URL de la tarea:").grid(row=0, column=0, sticky="w", **pad)
        self.ent_url = ttk.Entry(marco, textvariable=self.url)
        self.ent_url.grid(row=0, column=1, sticky="ew", **pad)
        self.btn_urls = ttk.Button(marco, text="Tareas del lote…", command=self._popup_urls, state="disabled")
        self.btn_urls.grid(row=0, column=2, **pad)
        self.lbl_info_url = ttk.Label(
            marco,
            text=TEXTO_URL,
            foreground="#555", wraplength=720,
        )
        self.lbl_info_url.grid(row=1, column=0, columnspan=3, sticky="w", **pad)

        marco = ttk.LabelFrame(tab, text="Opciones")
        marco.pack(fill="x", **pad)
        self.chk_confirmar = ttk.Checkbutton(
            marco, text="Pedir confirmación antes de guardar o sustituir (recomendado)", variable=self.confirmar)
        self.chk_confirmar.pack(anchor="w", **pad)
        ttk.Checkbutton(marco, text="Sobrescribir la rúbrica si la tarea ya tiene una",
                        variable=self.reemplazar).pack(anchor="w", **pad)
        ttk.Checkbutton(marco, text="Guardar como borrador", variable=self.borrador).pack(anchor="w", **pad)
        ttk.Checkbutton(marco, text="Forzar nuevo inicio de sesión", variable=self.nueva_sesion).pack(anchor="w", **pad)
        ttk.Checkbutton(marco, text="Solo validar (no abre Moodle)", variable=self.solo_validar).pack(anchor="w", **pad)
        fila = ttk.Frame(marco)
        fila.pack(anchor="w", **pad)
        ttk.Label(fila, text="Navegador:").pack(side="left")
        ttk.Combobox(fila, textvariable=self.navegador, state="readonly", width=12,
                     values=["chromium", "chrome", "msedge"]).pack(side="left", padx=6)

        fila = ttk.Frame(tab)
        fila.pack(fill="x", **pad)
        self.btn_importar = ttk.Button(fila, text="Importar", command=self._importar)
        self.btn_importar.pack(side="left")
        self.btn_parar = ttk.Button(fila, text="Detener", command=self._detener, state="disabled")
        self.btn_parar.pack(side="left", padx=6)

        marco = ttk.LabelFrame(tab, text="Salida")
        marco.pack(fill="both", expand=True, **pad)
        self.salida = tk.Text(marco, height=12, wrap="word", state="disabled")
        barra = ttk.Scrollbar(marco, command=self.salida.yview)
        self.salida.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.salida.pack(fill="both", expand=True)

        fila = ttk.Frame(tab)
        fila.pack(fill="x", **pad)
        self.entrada = ttk.Entry(fila, state="disabled")
        self.entrada.pack(side="left", fill="x", expand=True)
        self.entrada.bind("<Return>", lambda _e: self._enviar(self.entrada.get()))
        self.botones_resp = [
            ttk.Button(fila, text="Enviar", command=lambda: self._enviar(self.entrada.get())),
            ttk.Button(fila, text="Sí", command=lambda: self._enviar("s")),
            ttk.Button(fila, text="No", command=lambda: self._enviar("n")),
            ttk.Button(fila, text="Intro", command=lambda: self._enviar("")),
        ]
        for b in self.botones_resp:
            b.pack(side="left", padx=2)
            b.state(["disabled"])

    # ------------------------------------------------------------ acciones
    def _examinar(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Selecciona la rúbrica",
            filetypes=[("Rúbrica", "*.json *.xlsx"), ("JSON", "*.json"), ("Excel", "*.xlsx")],
        )
        if ruta:
            self.fichero.set(ruta)
            self._actualizar_vista()

    # ------------------------------------------------------ vista previa
    def _construir_vista_previa(self) -> None:
        self.ultima_vista: str | None = None
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Vista previa")
        self.lbl_estado = tk.Label(tab, anchor="w", justify="left", wraplength=740, padx=8, pady=6, text=TEXTO_VACIO)
        self.lbl_estado.pack(fill="x")

        self.nav = ttk.Frame(tab)
        ttk.Button(self.nav, text="◀ Anterior", command=lambda: self._ir(-1)).pack(side="left", padx=4)
        ttk.Button(self.nav, text="Siguiente ▶", command=lambda: self._ir(1)).pack(side="left", padx=4)
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
            self.lbl_nav.configure(text=f"Rúbrica {i + 1} de {len(self.marcos)} · {self.items[i]['etiqueta']}")

    def _ir(self, delta: int) -> None:
        if not self.marcos:
            return
        self.update_idletasks()
        i = min(max(self._indice_actual() + delta, 0), len(self.marcos) - 1)
        total = max(self.tabla.winfo_height(), 1)
        self.lienzo.yview_moveto(self.marcos[i].winfo_y() / total)

    # --- carga de datos (JSON individual, lote o Excel)
    def _items_desde_json(self, datos: Any) -> tuple[list[tuple[str, Any]], bool]:
        if isinstance(datos, dict) and "tareas" in datos and isinstance(datos["tareas"], list):
            return [(f"Tarea {t.get('numero', i)}", convertir(t, "UD2"))
                    for i, t in enumerate(datos["tareas"], 1)], True
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
                    return [], False, (r.stderr or r.stdout).strip() or "No se pudo convertir el Excel."
                return [("", json.loads(destino.read_text(encoding="utf-8")))], False, None
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as e:
            return [], False, f"JSON mal formado (línea {e.lineno}, columna {e.colno}): {e.msg}"
        except (OSError, UnicodeDecodeError) as e:
            return [], False, str(e)
        try:
            elementos, lote = self._items_desde_json(datos)
        except (KeyError, TypeError, ValueError) as e:
            return [], False, f"Estructura no reconocida: {e!r}"
        return elementos, lote, None

    @staticmethod
    def _validar(datos: Any, nombre: str, original: Path | None) -> list[str]:
        errores: list[str] = []
        if not isinstance(datos, dict):
            return ["La rúbrica debe ser un objeto JSON."]
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
            errores.append(f"Valor inesperado: {e}")
        return errores + avisos_estructura(datos)

    def _actualizar_vista(self, forzar: bool = False) -> None:
        texto = self.fichero.get().strip().strip('"')
        if not forzar and texto == self.ultima_vista:
            return
        self.ultima_vista = texto
        previas = {it["etiqueta"]: it["url"].get() for it in self.items}
        for w in self.tabla.winfo_children():
            w.destroy()
        self.marcos = []
        self.items = []
        self.es_lote = False
        self.nav.pack_forget()
        ruta = Path(texto)
        if not texto or not ruta.is_file():
            self.lbl_estado.configure(bg=self.cget("bg"), fg="black", text=TEXTO_VACIO)
            self._aplicar_modo()
            return

        elementos, self.es_lote, error = self._leer_fichero(ruta)
        if error:
            self.lbl_estado.configure(bg="#fde2e2", fg="#8a1111", text="✗ Rúbrica NO válida:\n• " + error)
            self._aplicar_modo()
            return

        for i, (etiqueta, datos) in enumerate(elementos, 1):
            nombre = (re.sub(r"[^\w\-]+", "_", etiqueta) if etiqueta else ruta.stem) + ".json"
            original = ruta if (not self.es_lote and ruta.suffix.lower() == ".json") else None
            errores = self._validar(datos, nombre, original)
            url = tk.StringVar(value=previas.get(etiqueta) or url_de(datos))
            self.items.append({"etiqueta": etiqueta or ruta.stem, "datos": datos, "errores": errores, "url": url})

        invalidas = [it for it in self.items if it["errores"]]
        if self.es_lote:
            n = len(self.items)
            if invalidas:
                self.lbl_estado.configure(
                    bg="#fde2e2", fg="#8a1111",
                    text=f"✗ Lote de {n} rúbricas: {len(invalidas)} NO válidas "
                         f"({', '.join(it['etiqueta'] for it in invalidas)}).")
            else:
                self.lbl_estado.configure(bg="#dff3e0", fg="#14571b", text=f"✓ Lote de {n} rúbricas, todas válidas.")
            self.nav.pack(fill="x", before=self.cuerpo)
        elif invalidas:
            self.lbl_estado.configure(bg="#fde2e2", fg="#8a1111",
                                      text="✗ Rúbrica NO válida:\n• " + "\n• ".join(invalidas[0]["errores"]))
        else:
            self.lbl_estado.configure(bg="#dff3e0", fg="#14571b", text="✓ Estructura válida.")

        for i, it in enumerate(self.items, 1):
            marco = tk.Frame(self.tabla, bd=0)
            marco.pack(fill="x", anchor="nw", pady=(0, 18))
            self.marcos.append(marco)
            if self.es_lote:
                ok = not it["errores"]
                tk.Label(marco, anchor="w", justify="left", wraplength=740, padx=8, pady=4,
                         font=("Segoe UI", 10, "bold"),
                         bg="#dff3e0" if ok else "#fde2e2", fg="#14571b" if ok else "#8a1111",
                         text=f"{i}/{len(self.items)} · {it['etiqueta']}  —  "
                              + ("✓ válida" if ok else "✗ NO válida:\n• " + "\n• ".join(it["errores"]))
                         ).pack(fill="x")
            if isinstance(it["datos"], dict):
                self._dibujar(marco, it["datos"])
        self._aplicar_modo()
        self.after(100, self._actualizar_nav)

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
            self.lbl_info_url.configure(text=TEXTO_URL)

    def _actualizar_info_urls(self) -> None:
        con_url = sum(1 for it in self.items if it["url"].get().strip())
        self.lbl_info_url.configure(
            text=f"Lote de {len(self.items)} rúbricas: cada una tiene su propia tarea ({con_url} con URL). "
                 "Pulsa «Tareas del lote…» para configurarlas; las que no tengan URL se omiten. "
                 "En un lote la confirmación antes de guardar es siempre obligatoria.")

    def _celda(self, parent: tk.Frame, fila: int, col: int, texto: str, ancho: int, **kw) -> None:
        opciones = dict(text=texto, wraplength=ancho, justify="left", anchor="nw", padx=6, pady=4,
                        bg="white", relief="solid", bd=1)
        opciones.update(kw)
        tk.Label(parent, **opciones).grid(row=fila, column=col, sticky="nsew")

    def _dibujar(self, parent: tk.Frame, datos: dict) -> None:
        tabla = tk.Frame(parent)
        tabla.pack(fill="x", anchor="nw")
        crit = datos.get("criterios") if isinstance(datos.get("criterios"), list) else []
        crit = [c for c in crit if isinstance(c, dict)]
        niveles = [c.get("niveles") if isinstance(c.get("niveles"), list) else [] for c in crit]
        n_cols = max([len(n) for n in niveles] + [1])
        ancho = max(140, min(260, 760 // n_cols))

        def num(x: Any) -> bool:
            return isinstance(x, (int, float)) and not isinstance(x, bool)

        total = sum(
            max([x["puntos"] for x in n if isinstance(x, dict) and num(x.get("puntos"))] or [0]) for n in niveles
        )
        sub = f"Puntuación máxima: {pts(total)}"
        if datos.get("puntuacion_maxima") is not None:
            sub += f" (declarada: {pts(datos['puntuacion_maxima'])})"
        sub += f" · {len(crit)} criterios"
        sub += f"\nTarea Moodle: {url_de(datos) or '— (se pedirá o se configurará al importar)'}"
        if datos.get("descripcion"):
            sub += f"\n{datos['descripcion']}"
        tk.Label(tabla, text=f"{datos.get('nombre') or '(sin nombre)'}\n{sub}", wraplength=ancho * (n_cols + 1),
                 justify="left", anchor="nw", padx=6, pady=4, bg="#e8eef7", relief="solid", bd=1,
                 font=("Segoe UI", 10)).grid(row=0, column=0, columnspan=n_cols + 1, sticky="nsew")

        negrita = ("Segoe UI", 9, "bold")
        self._celda(tabla, 1, 0, "Criterio", ancho, bg="#f0f0f0", font=negrita)
        for j in range(n_cols):
            nombre = ""
            for n in niveles:
                if j < len(n) and isinstance(n[j], dict) and n[j].get("nombre"):
                    nombre = str(n[j]["nombre"])
                    break
            self._celda(tabla, 1, j + 1, nombre or f"Nivel {j + 1}", ancho, bg="#f0f0f0", font=negrita)

        for i, (c, niv) in enumerate(zip(crit, niveles), start=2):
            self._celda(tabla, i, 0, str(c.get("descripcion") or "⚠ (sin descripción)"), ancho, font=negrita)
            for j in range(n_cols):
                if j < len(niv) and isinstance(niv[j], dict):
                    x = niv[j]
                    definicion = x.get("definicion") or "⚠ (sin definición)"
                    self._celda(tabla, i, j + 1, f"{definicion}\n\n{pts(x.get('puntos'))} puntos", ancho)
                else:
                    self._celda(tabla, i, j + 1, "", ancho, bg="#f6f6f6")

    # --- URLs del lote
    def _popup_urls(self) -> None:
        if not self.es_lote or not self.items:
            return
        top = tk.Toplevel(self)
        top.title("Tareas de Moodle del lote")
        top.transient(self)
        top.geometry(f"820x{min(150 + 38 * len(self.items), 600)}")
        top.grab_set()

        ttk.Label(top, wraplength=780, foreground="#555",
                  text="URL completa de la tarea (…/mod/assign/view.php?id=NNN) para cada rúbrica. "
                       "Las ya informadas en el JSON aparecen rellenas; las vacías se omitirán al importar."
                  ).pack(fill="x", padx=10, pady=8)

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
            ttk.Label(celda, text=nombre + ("  ✗ NO válida" if it["errores"] else ""),
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
                    messagebox.showerror("URL no válida", f"{it['etiqueta']}: {e}", parent=top)
                    return
            for it, v in zip(self.items, variables):
                it["url"].set(v.get().strip())
            self._actualizar_info_urls()
            lienzo.unbind_all("<MouseWheel>")
            top.destroy()

        botones = ttk.Frame(top)
        botones.pack(fill="x", padx=10, pady=8)
        ttk.Button(botones, text="Aceptar", command=aceptar).pack(side="right")
        ttk.Button(botones, text="Cancelar", command=lambda: (lienzo.unbind_all("<MouseWheel>"), top.destroy())
                   ).pack(side="right", padx=6)

    # ------------------------------------------------------- importación
    def _escribir(self, texto: str) -> None:
        self.salida.configure(state="normal")
        self.salida.insert("end", texto)
        self.salida.see("end")
        self.salida.configure(state="disabled")

    def _estado_ejecucion(self, ejecutando: bool) -> None:
        self.btn_importar.state(["disabled" if ejecutando else "!disabled"])
        self.btn_parar.state(["!disabled" if ejecutando else "disabled"])
        self.entrada.configure(state="normal" if ejecutando else "disabled")
        for b in self.botones_resp:
            b.state(["!disabled" if ejecutando else "disabled"])

    def _preparar_json(self, ruta: Path) -> Path | None:
        if ruta.suffix.lower() == ".json":
            return ruta
        if ruta.suffix.lower() not in (".xlsx", ".xlsm"):
            messagebox.showerror("Formato no soportado", "Selecciona un fichero .json o .xlsx.")
            return None
        self.tmpdir = Path(tempfile.mkdtemp(prefix="rubrica_"))
        destino = self.tmpdir / (ruta.stem + ".json")
        r = subprocess.run(
            [python_consola(), str(XLSX2JSON), str(ruta), str(destino)],
            capture_output=True, text=True, encoding="utf-8", creationflags=SIN_VENTANA, env=ENV_UTF8,
        )
        self._escribir(f"Conversión de Excel a JSON temporal:\n{r.stdout}{r.stderr}")
        if r.returncode != 0:
            self._limpiar_tmp()
            return None
        return destino

    def _opciones_comunes(self) -> list[str]:
        cmd: list[str] = []
        if self.reemplazar.get():
            cmd.append("--reemplazar")
        if self.borrador.get():
            cmd.append("--borrador")
        return cmd

    def _importar(self) -> None:
        ruta = Path(self.fichero.get().strip().strip('"'))
        if not ruta.is_file():
            messagebox.showerror("Falta la rúbrica", "Selecciona un fichero de rúbrica existente.")
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
                messagebox.showerror("URL no válida", str(e))
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
            messagebox.showerror("Lote con rúbricas no válidas",
                                 "Corrige estas rúbricas antes de importar:\n• " + "\n• ".join(invalidas))
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
                messagebox.showerror("URL no válida", f"{it['etiqueta']}: {e}")
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
                messagebox.showinfo("Faltan las tareas", "Indica la URL de la tarea de cada rúbrica.")
                self._popup_urls()
                return
            if sin_url and not messagebox.askyesno(
                    "Rúbricas sin tarea",
                    f"{len(sin_url)} rúbricas no tienen URL y se omitirán:\n• " + "\n• ".join(sin_url)
                    + "\n\n¿Continuar con el resto?"):
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
            self._escribir(f"\n=== {etiqueta} (quedan {len(self.trabajos)} después de esta) ===\n")
        self._escribir("$ " + " ".join(cmd) + "\n\n")
        try:
            self.proceso = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=str(AQUI), creationflags=SIN_VENTANA, env=ENV_UTF8,
            )
        except OSError as e:
            messagebox.showerror("No se pudo ejecutar", str(e))
            self.trabajos = []
            self._estado_ejecucion(False)
            self._limpiar_tmp()
            return
        self._estado_ejecucion(True)
        threading.Thread(target=self._leer, args=(self.proceso,), daemon=True).start()

    def _leer(self, proc: subprocess.Popen) -> None:
        # Lee byte a byte para mostrar también los prompts, que no terminan en salto de línea.
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        while True:
            dato = proc.stdout.read(1)
            if not dato:
                break
            self.cola.put(decoder.decode(dato))
        proc.wait()
        self.cola.put(None)

    def _vaciar_cola(self) -> None:
        try:
            while True:
                item = self.cola.get_nowait()
                if item is None:
                    codigo = self.proceso.returncode if self.proceso else "?"
                    self._escribir(f"\n[Proceso terminado, código {codigo}]\n")
                    self.proceso = None
                    if self.trabajos and not self.lote_detenido:
                        self._lanzar_siguiente()
                    else:
                        if self.trabajos:
                            self._escribir(f"[Lote detenido: {len(self.trabajos)} rúbricas sin procesar]\n")
                        elif self.es_lote:
                            self._escribir("[Lote terminado]\n")
                        self.trabajos = []
                        self._estado_ejecucion(False)
                        self._limpiar_tmp()
                else:
                    self._escribir(item)
        except queue.Empty:
            pass
        self.after(50, self._vaciar_cola)

    def _enviar(self, texto: str) -> None:
        if not self.proceso or self.proceso.stdin is None:
            return
        try:
            self.proceso.stdin.write((texto + "\n").encode("utf-8"))
            self.proceso.stdin.flush()
        except OSError:
            return
        self._escribir(f"{texto}\n")
        self.entrada.delete(0, "end")

    def _detener(self) -> None:
        self.lote_detenido = True
        if self.proceso:
            self.proceso.terminate()

    def _limpiar_tmp(self) -> None:
        if self.tmpdir:
            shutil.rmtree(self.tmpdir, ignore_errors=True)
            self.tmpdir = None

    def _cerrar(self) -> None:
        if self.proceso:
            if not messagebox.askyesno("Importación en curso", "¿Detener la importación y salir?"):
                return
            self.lote_detenido = True
            self.proceso.terminate()
        self._limpiar_tmp()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
