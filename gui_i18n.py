"""Textos de la interfaz gráfica en gallego (gl), español (es) e inglés (en)."""
from __future__ import annotations

IDIOMAS = ("gl", "es", "en")
IDIOMA_POR_DEFECTO = "es"
_actual = IDIOMA_POR_DEFECTO

TEXTOS: dict[str, dict[str, str]] = {
    "es": {
        "app_titulo": "Importar rúbrica en Moodle",
        "menu_archivo": "Archivo", "menu_salir": "Salir",
        "menu_ayuda": "Ayuda", "menu_acerca": "Acerca de…", "about_titulo": "Acerca de Importar rúbrica",
        "about_autor": "Autor: Rubén García", "about_licencia": "Licencia:",
        "about_proyecto": "Proyecto en GitHub:", "btn_cerrar": "Cerrar",
        "menu_config": "Configuración", "menu_idioma": "Idioma",
        "lang_gl": "Gallego", "lang_es": "Español", "lang_en": "Inglés",

        "grp_rubrica": "Rúbrica", "lbl_fichero": "Fichero (.json / .xlsx):",
        "btn_examinar": "📂  Examinar…", "btn_recargar": "🔄  Recargar",
        "tab_importar": "Importar", "tab_vista": "Vista previa",
        "grp_tarea": "Tarea de Moodle", "lbl_url": "URL de la tarea:", "btn_lote": "📋  Tareas del lote…",
        "grp_opciones": "Opciones",
        "chk_confirmar": "Pedir confirmación antes de guardar o sustituir (recomendado)",
        "chk_borrador": "Guardar como borrador", "chk_sesion": "Forzar nuevo inicio de sesión",
        "chk_validar": "Solo validar (no abre Moodle)", "lbl_navegador": "Navegador:",
        "btn_importar": "▶  Importar", "btn_detener": "⏹  Detener", "btn_limpiar": "🧹  Limpiar logs",
        "spinner": "Importando…", "grp_logs": "Logs de ejecución",
        "nav_anterior": "◀ Anterior", "nav_siguiente": "Siguiente ▶",

        "texto_url": "URL completa de la tarea (…/mod/assign/view.php?id=NNN). "
                     "Vacío = se usa la del fichero o el script la pregunta.",
        "texto_vacio": "Selecciona un fichero de rúbrica para previsualizarlo.",
        "info_lote": "Lote de {n} rúbricas: cada una tiene su propia tarea ({con_url} con URL). "
                     "Pulsa «Tareas del lote…» para configurarlas; las que no tengan URL se omiten. "
                     "En un lote la confirmación antes de guardar es siempre obligatoria.",
        "estado_no_valida": "✗ Rúbrica NO válida:\n• {detalle}",
        "estado_lote_invalido": "✗ Lote de {n} rúbricas: {k} NO válidas ({lista}).",
        "estado_lote_ok": "✓ Lote de {n} rúbricas, todas válidas.",
        "estado_ok": "✓ Estructura válida.",
        "item_valida": "✓ válida", "item_no_valida": "✗ NO válida:\n• {detalle}",
        "nav_rubrica": "Rúbrica {i} de {n} · {etiqueta}",
        "tarea_n": "Tarea {n}",

        "max_puntos": "Puntuación máxima: {p}", "declarada": " (declarada: {p})",
        "n_criterios": " · {n} criterios",
        "tarea_moodle": "Tarea Moodle: {url}", "tarea_pendiente": "— (se pedirá o se configurará al importar)",
        "sin_nombre": "(sin nombre)", "col_criterio": "Criterio", "nivel_n": "Nivel {n}",
        "sin_descripcion": "⚠ (sin descripción)", "sin_definicion": "⚠ (sin definición)",
        "puntos": "{p} puntos",
        "lbl_nombre": "Nombre:", "lbl_puntos": "Puntos:",
        "descartar_t": "Descartar cambios",
        "descartar": "Tienes ediciones sin guardar en la vista previa. ¿Quieres descartarlas?",
        "guardar_t": "Guardar cambios", "guardar_como_t": "Guardar rúbrica como",
        "guardar_txt": "Has editado la rúbrica en la vista previa. ¿Qué quieres hacer con los cambios?",
        "guardar_no_sobrescribir": "(No se puede sobrescribir el original con este formato.)",
        "guardado": "Guardado en:\n{ruta}",
        "btn_sobrescribir": "Sobrescribir original", "btn_guardar_como": "Guardar como…", "btn_nada": "No hacer nada",

        "aviso_niveles": "Criterio {i}: tiene {n} niveles y la escala indica {esc}.",
        "aviso_nombres": "Criterio {i}: los nombres de nivel no coinciden con la escala.",
        "err_url_id": "Indica la URL completa de la tarea (…/mod/assign/view.php?id=NNN), no solo el id.",
        "err_objeto": "La rúbrica debe ser un objeto JSON.", "err_valor": "Valor inesperado: {e}",
        "err_excel": "No se pudo convertir el Excel.",
        "err_json": "JSON mal formado (línea {l}, columna {c}): {m}",
        "err_estructura": "Estructura no reconocida: {e}",

        "popup_titulo": "Tareas de Moodle del lote",
        "popup_desc": "URL completa de la tarea (…/mod/assign/view.php?id=NNN) para cada rúbrica. "
                      "Las ya informadas en el JSON aparecen rellenas; las vacías se omitirán al importar.",
        "popup_aceptar": "✔  Aceptar", "popup_cancelar": "✖  Cancelar",
        "dlg_examinar": "Selecciona la rúbrica", "ft_rubrica": "Rúbrica",

        "t_imp": "Importar rúbrica",
        "err_url_t": "URL no válida",
        "err_formato_t": "Formato no soportado", "err_formato": "Selecciona un fichero .json o .xlsx.",
        "err_falta_t": "Falta la rúbrica", "err_falta": "Selecciona un fichero de rúbrica existente.",
        "conv_excel": "Conversión de Excel a JSON temporal:",
        "err_lote_t": "Lote con rúbricas no válidas", "err_lote": "Corrige estas rúbricas antes de importar:",
        "faltan_t": "Faltan las tareas", "faltan": "Indica la URL de la tarea de cada rúbrica.",
        "sin_tarea_t": "Rúbricas sin tarea",
        "sin_tarea": "{n} rúbricas no tienen URL y se omitirán:", "sin_tarea_fin": "¿Continuar con el resto?",
        "no_ejecuta_t": "No se pudo ejecutar",
        "lote_cab": "=== {etiqueta} (quedan {n} después de esta) ===",
        "proc_fin": "[Proceso terminado, código {c}]",
        "lote_detenido": "[Lote detenido: {n} rúbricas sin procesar]", "lote_fin": "[Lote terminado]",
        "resp_si": "Sí", "resp_no": "No",
        "salir_t": "Importación en curso", "salir": "¿Detener la importación y salir?",

        "p_resumen": "Rúbrica «{nombre}» · {n} criterios · máximo {max} p",
        "p_falta_pw": "Falta Playwright. Instálalo con:\n  pip install playwright\n"
                      "  python -m playwright install chromium",
        "p_login": "\n  → Inicia sesión en la ventana del navegador con tus datos.\n"
                   "    El script continuará solo en cuanto entres en Moodle.",
        "p_tarea": "  · Tarea: {titulo}",
        "p_existente": "\n  ! Esta tarea YA TIENE una rúbrica; se sustituirá al guardar.",
        "p_sobrescribe": "  · La rúbrica existente se sobrescribirá al guardar.",
        "p_criterio": "  · Criterio {i}/{n}: {descripcion}",
        "p_opcion": "  ! Opción «{opcion}» no encontrada en esta versión de Moodle; se ignora.",
        "p_guardada": "  ✓ Rúbrica «{nombre}» guardada.\n    Recuerda: Moodle escala la puntuación de la "
                      "rúbrica a la calificación máxima de la tarea.",
        "p_inesperado": "  ✗ Error inesperado: {d}", "p_captura": "\n    Captura guardada en {c}",

        "login_cab": "Inicia sesión en Moodle",
        "login_txt": "Se ha abierto el navegador. Introduce tus datos allí; la importación "
                     "continuará sola en cuanto entres en Moodle.",
        "ok_guardada": "Rúbrica «{nombre}» guardada.\n\nMoodle escala la puntuación de la rúbrica "
                       "a la calificación máxima de la tarea.",
        "q_sustituir": "Esta tarea ya tiene una rúbrica.\n\nSe sustituirá su contenido cuando confirmes el "
                       "guardado. Si ya has calificado con ella, Moodle puede marcar esas calificaciones "
                       "para revisar.\n\n¿Continuar y preparar la sustitución?",
        "q_guardar": "El editor de Moodle ya está relleno. Compruébalo en el navegador "
                     "(NO pulses guardar allí).\n\n¿Guardar la rúbrica ahora?",
        "q_fin": "Importación terminada.\n\nEl navegador seguirá abierto hasta que aceptes este mensaje.",
        "q_url_t": "Importar rúbrica · Tarea de Moodle",
        "q_url": "¿En qué tarea de Moodle va la rúbrica «{rubrica}»?\n\n"
                 "Pega la URL de la tarea (…/mod/assign/view.php?id=NNN) o solo el número id.",
    },
    "gl": {
        "app_titulo": "Importar rúbrica en Moodle",
        "menu_archivo": "Arquivo", "menu_salir": "Saír",
        "menu_ayuda": "Axuda", "menu_acerca": "Acerca de…", "about_titulo": "Acerca de Importar rúbrica",
        "about_autor": "Autor: Rubén García", "about_licencia": "Licenza:",
        "about_proyecto": "Proxecto en GitHub:", "btn_cerrar": "Pechar",
        "menu_config": "Configuración", "menu_idioma": "Idioma",
        "lang_gl": "Galego", "lang_es": "Español", "lang_en": "Inglés",

        "grp_rubrica": "Rúbrica", "lbl_fichero": "Ficheiro (.json / .xlsx):",
        "btn_examinar": "📂  Examinar…", "btn_recargar": "🔄  Recargar",
        "tab_importar": "Importar", "tab_vista": "Vista previa",
        "grp_tarea": "Tarefa de Moodle", "lbl_url": "URL da tarefa:", "btn_lote": "📋  Tarefas do lote…",
        "grp_opciones": "Opcións",
        "chk_confirmar": "Pedir confirmación antes de gardar ou substituír (recomendado)",
        "chk_borrador": "Gardar como borrador", "chk_sesion": "Forzar novo inicio de sesión",
        "chk_validar": "Só validar (non abre Moodle)", "lbl_navegador": "Navegador:",
        "btn_importar": "▶  Importar", "btn_detener": "⏹  Deter", "btn_limpiar": "🧹  Limpar logs",
        "spinner": "Importando…", "grp_logs": "Logs de execución",
        "nav_anterior": "◀ Anterior", "nav_siguiente": "Seguinte ▶",

        "texto_url": "URL completa da tarefa (…/mod/assign/view.php?id=NNN). "
                     "Baleiro = úsase a do ficheiro ou o script pregúntaa.",
        "texto_vacio": "Selecciona un ficheiro de rúbrica para previsualizalo.",
        "info_lote": "Lote de {n} rúbricas: cada unha ten a súa propia tarefa ({con_url} con URL). "
                     "Preme «Tarefas do lote…» para configuralas; as que non teñan URL omítense. "
                     "Nun lote a confirmación antes de gardar é sempre obrigatoria.",
        "estado_no_valida": "✗ Rúbrica NON válida:\n• {detalle}",
        "estado_lote_invalido": "✗ Lote de {n} rúbricas: {k} NON válidas ({lista}).",
        "estado_lote_ok": "✓ Lote de {n} rúbricas, todas válidas.",
        "estado_ok": "✓ Estrutura válida.",
        "item_valida": "✓ válida", "item_no_valida": "✗ NON válida:\n• {detalle}",
        "nav_rubrica": "Rúbrica {i} de {n} · {etiqueta}",
        "tarea_n": "Tarefa {n}",

        "max_puntos": "Puntuación máxima: {p}", "declarada": " (declarada: {p})",
        "n_criterios": " · {n} criterios",
        "tarea_moodle": "Tarefa Moodle: {url}", "tarea_pendiente": "— (pedirase ou configurarase ao importar)",
        "sin_nombre": "(sen nome)", "col_criterio": "Criterio", "nivel_n": "Nivel {n}",
        "sin_descripcion": "⚠ (sen descrición)", "sin_definicion": "⚠ (sen definición)",
        "puntos": "{p} puntos",
        "lbl_nombre": "Nome:", "lbl_puntos": "Puntos:",
        "descartar_t": "Descartar cambios",
        "descartar": "Tes edicións sen gardar na vista previa. Queres descartalas?",
        "guardar_t": "Gardar cambios", "guardar_como_t": "Gardar rúbrica como",
        "guardar_txt": "Editaches a rúbrica na vista previa. Que queres facer cos cambios?",
        "guardar_no_sobrescribir": "(Non se pode sobrescribir o orixinal con este formato.)",
        "guardado": "Gardado en:\n{ruta}",
        "btn_sobrescribir": "Sobrescribir orixinal", "btn_guardar_como": "Gardar como…", "btn_nada": "Non facer nada",

        "aviso_niveles": "Criterio {i}: ten {n} niveis e a escala indica {esc}.",
        "aviso_nombres": "Criterio {i}: os nomes de nivel non coinciden coa escala.",
        "err_url_id": "Indica a URL completa da tarefa (…/mod/assign/view.php?id=NNN), non só o id.",
        "err_objeto": "A rúbrica debe ser un obxecto JSON.", "err_valor": "Valor inesperado: {e}",
        "err_excel": "Non se puido converter o Excel.",
        "err_json": "JSON mal formado (liña {l}, columna {c}): {m}",
        "err_estructura": "Estrutura non recoñecida: {e}",

        "popup_titulo": "Tarefas de Moodle do lote",
        "popup_desc": "URL completa da tarefa (…/mod/assign/view.php?id=NNN) para cada rúbrica. "
                      "As xa informadas no JSON aparecen cubertas; as baleiras omitiranse ao importar.",
        "popup_aceptar": "✔  Aceptar", "popup_cancelar": "✖  Cancelar",
        "dlg_examinar": "Selecciona a rúbrica", "ft_rubrica": "Rúbrica",

        "t_imp": "Importar rúbrica",
        "err_url_t": "URL non válida",
        "err_formato_t": "Formato non soportado", "err_formato": "Selecciona un ficheiro .json ou .xlsx.",
        "err_falta_t": "Falta a rúbrica", "err_falta": "Selecciona un ficheiro de rúbrica existente.",
        "conv_excel": "Conversión de Excel a JSON temporal:",
        "err_lote_t": "Lote con rúbricas non válidas", "err_lote": "Corrixe estas rúbricas antes de importar:",
        "faltan_t": "Faltan as tarefas", "faltan": "Indica a URL da tarefa de cada rúbrica.",
        "sin_tarea_t": "Rúbricas sen tarefa",
        "sin_tarea": "{n} rúbricas non teñen URL e omitiranse:", "sin_tarea_fin": "Continuar co resto?",
        "no_ejecuta_t": "Non se puido executar",
        "lote_cab": "=== {etiqueta} (quedan {n} despois desta) ===",
        "proc_fin": "[Proceso terminado, código {c}]",
        "lote_detenido": "[Lote detido: {n} rúbricas sen procesar]", "lote_fin": "[Lote terminado]",
        "resp_si": "Si", "resp_no": "Non",
        "salir_t": "Importación en curso", "salir": "Deter a importación e saír?",

        "p_resumen": "Rúbrica «{nombre}» · {n} criterios · máximo {max} p",
        "p_falta_pw": "Falta Playwright. Instálao con:\n  pip install playwright\n"
                      "  python -m playwright install chromium",
        "p_login": "\n  → Inicia sesión na xanela do navegador cos teus datos.\n"
                   "    O script continuará só en canto entres en Moodle.",
        "p_tarea": "  · Tarefa: {titulo}",
        "p_existente": "\n  ! Esta tarefa XA TEN unha rúbrica; substituirase ao gardar.",
        "p_sobrescribe": "  · A rúbrica existente sobrescribirase ao gardar.",
        "p_criterio": "  · Criterio {i}/{n}: {descripcion}",
        "p_opcion": "  ! Opción «{opcion}» non atopada nesta versión de Moodle; ignórase.",
        "p_guardada": "  ✓ Rúbrica «{nombre}» gardada.\n    Lembra: Moodle escala a puntuación da "
                      "rúbrica á cualificación máxima da tarefa.",
        "p_inesperado": "  ✗ Erro inesperado: {d}", "p_captura": "\n    Captura gardada en {c}",

        "login_cab": "Inicia sesión en Moodle",
        "login_txt": "Abriuse o navegador. Introduce os teus datos alí; a importación "
                     "continuará soa en canto entres en Moodle.",
        "ok_guardada": "Rúbrica «{nombre}» gardada.\n\nMoodle escala a puntuación da rúbrica "
                       "á cualificación máxima da tarefa.",
        "q_sustituir": "Esta tarefa xa ten unha rúbrica.\n\nSubstituirase o seu contido cando confirmes o "
                       "gardado. Se xa cualificaches con ela, Moodle pode marcar esas cualificacións "
                       "para revisar.\n\nContinuar e preparar a substitución?",
        "q_guardar": "O editor de Moodle xa está cuberto. Compróbao no navegador "
                     "(NON premas gardar alí).\n\nGardar a rúbrica agora?",
        "q_fin": "Importación terminada.\n\nO navegador seguirá aberto ata que aceptes esta mensaxe.",
        "q_url_t": "Importar rúbrica · Tarefa de Moodle",
        "q_url": "En que tarefa de Moodle vai a rúbrica «{rubrica}»?\n\n"
                 "Pega a URL da tarefa (…/mod/assign/view.php?id=NNN) ou só o número id.",
    },
    "en": {
        "app_titulo": "Import rubric into Moodle",
        "menu_archivo": "File", "menu_salir": "Exit",
        "menu_ayuda": "Help", "menu_acerca": "About…", "about_titulo": "About Import rubric",
        "about_autor": "Author: Rubén García", "about_licencia": "License:",
        "about_proyecto": "GitHub project:", "btn_cerrar": "Close",
        "menu_config": "Settings", "menu_idioma": "Language",
        "lang_gl": "Galician", "lang_es": "Spanish", "lang_en": "English",

        "grp_rubrica": "Rubric", "lbl_fichero": "File (.json / .xlsx):",
        "btn_examinar": "📂  Browse…", "btn_recargar": "🔄  Reload",
        "tab_importar": "Import", "tab_vista": "Preview",
        "grp_tarea": "Moodle assignment", "lbl_url": "Assignment URL:", "btn_lote": "📋  Batch assignments…",
        "grp_opciones": "Options",
        "chk_confirmar": "Ask for confirmation before saving or replacing (recommended)",
        "chk_borrador": "Save as draft", "chk_sesion": "Force a new login",
        "chk_validar": "Validate only (does not open Moodle)", "lbl_navegador": "Browser:",
        "btn_importar": "▶  Import", "btn_detener": "⏹  Stop", "btn_limpiar": "🧹  Clear logs",
        "spinner": "Importing…", "grp_logs": "Execution logs",
        "nav_anterior": "◀ Previous", "nav_siguiente": "Next ▶",

        "texto_url": "Full assignment URL (…/mod/assign/view.php?id=NNN). "
                     "Empty = the one in the file is used, or the script asks for it.",
        "texto_vacio": "Select a rubric file to preview it.",
        "info_lote": "Batch of {n} rubrics: each one has its own assignment ({con_url} with URL). "
                     "Press “Batch assignments…” to set them; those without a URL are skipped. "
                     "In a batch, confirmation before saving is always required.",
        "estado_no_valida": "✗ Rubric NOT valid:\n• {detalle}",
        "estado_lote_invalido": "✗ Batch of {n} rubrics: {k} NOT valid ({lista}).",
        "estado_lote_ok": "✓ Batch of {n} rubrics, all valid.",
        "estado_ok": "✓ Valid structure.",
        "item_valida": "✓ valid", "item_no_valida": "✗ NOT valid:\n• {detalle}",
        "nav_rubrica": "Rubric {i} of {n} · {etiqueta}",
        "tarea_n": "Task {n}",

        "max_puntos": "Maximum score: {p}", "declarada": " (declared: {p})",
        "n_criterios": " · {n} criteria",
        "tarea_moodle": "Moodle assignment: {url}", "tarea_pendiente": "— (will be asked for or set on import)",
        "sin_nombre": "(unnamed)", "col_criterio": "Criterion", "nivel_n": "Level {n}",
        "sin_descripcion": "⚠ (no description)", "sin_definicion": "⚠ (no definition)",
        "puntos": "{p} points",
        "lbl_nombre": "Name:", "lbl_puntos": "Points:",
        "descartar_t": "Discard changes",
        "descartar": "You have unsaved edits in the preview. Discard them?",
        "guardar_t": "Save changes", "guardar_como_t": "Save rubric as",
        "guardar_txt": "You edited the rubric in the preview. What do you want to do with the changes?",
        "guardar_no_sobrescribir": "(The original cannot be overwritten with this format.)",
        "guardado": "Saved to:\n{ruta}",
        "btn_sobrescribir": "Overwrite original", "btn_guardar_como": "Save as…", "btn_nada": "Do nothing",

        "aviso_niveles": "Criterion {i}: has {n} levels but the scale says {esc}.",
        "aviso_nombres": "Criterion {i}: level names do not match the scale.",
        "err_url_id": "Give the full assignment URL (…/mod/assign/view.php?id=NNN), not just the id.",
        "err_objeto": "The rubric must be a JSON object.", "err_valor": "Unexpected value: {e}",
        "err_excel": "The Excel file could not be converted.",
        "err_json": "Malformed JSON (line {l}, column {c}): {m}",
        "err_estructura": "Unrecognized structure: {e}",

        "popup_titulo": "Moodle assignments of the batch",
        "popup_desc": "Full assignment URL (…/mod/assign/view.php?id=NNN) for each rubric. "
                      "Those already set in the JSON are pre-filled; empty ones will be skipped on import.",
        "popup_aceptar": "✔  OK", "popup_cancelar": "✖  Cancel",
        "dlg_examinar": "Select the rubric", "ft_rubrica": "Rubric",

        "t_imp": "Import rubric",
        "err_url_t": "Invalid URL",
        "err_formato_t": "Unsupported format", "err_formato": "Select a .json or .xlsx file.",
        "err_falta_t": "Rubric missing", "err_falta": "Select an existing rubric file.",
        "conv_excel": "Excel to temporary JSON conversion:",
        "err_lote_t": "Batch with invalid rubrics", "err_lote": "Fix these rubrics before importing:",
        "faltan_t": "Assignments missing", "faltan": "Enter the assignment URL of each rubric.",
        "sin_tarea_t": "Rubrics without assignment",
        "sin_tarea": "{n} rubrics have no URL and will be skipped:", "sin_tarea_fin": "Continue with the rest?",
        "no_ejecuta_t": "Could not run",
        "lote_cab": "=== {etiqueta} ({n} left after this one) ===",
        "proc_fin": "[Process finished, code {c}]",
        "lote_detenido": "[Batch stopped: {n} rubrics not processed]", "lote_fin": "[Batch finished]",
        "resp_si": "Yes", "resp_no": "No",
        "salir_t": "Import in progress", "salir": "Stop the import and exit?",

        "p_resumen": "Rubric “{nombre}” · {n} criteria · maximum {max} pts",
        "p_falta_pw": "Playwright is missing. Install it with:\n  pip install playwright\n"
                      "  python -m playwright install chromium",
        "p_login": "\n  → Log in in the browser window with your credentials.\n"
                   "    The script will continue by itself as soon as you are in Moodle.",
        "p_tarea": "  · Assignment: {titulo}",
        "p_existente": "\n  ! This assignment ALREADY HAS a rubric; it will be replaced on save.",
        "p_sobrescribe": "  · The existing rubric will be overwritten on save.",
        "p_criterio": "  · Criterion {i}/{n}: {descripcion}",
        "p_opcion": "  ! Option “{opcion}” not found in this Moodle version; ignored.",
        "p_guardada": "  ✓ Rubric “{nombre}” saved.\n    Remember: Moodle scales the rubric score "
                      "to the maximum grade of the assignment.",
        "p_inesperado": "  ✗ Unexpected error: {d}", "p_captura": "\n    Screenshot saved at {c}",

        "login_cab": "Log in to Moodle",
        "login_txt": "The browser has been opened. Enter your credentials there; the import "
                     "will continue by itself as soon as you are in Moodle.",
        "ok_guardada": "Rubric “{nombre}” saved.\n\nMoodle scales the rubric score "
                       "to the maximum grade of the assignment.",
        "q_sustituir": "This assignment already has a rubric.\n\nIts content will be replaced when you confirm "
                       "the save. If you have already graded with it, Moodle may flag those grades "
                       "for review.\n\nContinue and prepare the replacement?",
        "q_guardar": "The Moodle editor is filled in. Check it in the browser "
                     "(do NOT click save there).\n\nSave the rubric now?",
        "q_fin": "Import finished.\n\nThe browser will stay open until you accept this message.",
        "q_url_t": "Import rubric · Moodle assignment",
        "q_url": "Which Moodle assignment does the rubric “{rubrica}” belong to?\n\n"
                 "Paste the assignment URL (…/mod/assign/view.php?id=NNN) or just the id number.",
    },
}


def set_idioma(codigo: str) -> str:
    global _actual
    _actual = codigo if codigo in TEXTOS else IDIOMA_POR_DEFECTO
    return _actual


def idioma() -> str:
    return _actual


def t(clave: str, **datos: object) -> str:
    texto = TEXTOS[_actual].get(clave) or TEXTOS[IDIOMA_POR_DEFECTO].get(clave) or clave
    return texto.format(**datos) if datos else texto
