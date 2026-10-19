# Importador de rúbricas a Moodle

Crea rúbricas en tareas de Moodle a partir de ficheros JSON. No necesita plugins ni
servicios web: el script abre un navegador y rellena el editor de rúbricas como lo
harías a mano. Tú inicias sesión con tus datos; el script nunca los pide ni los guarda.

Probado con Moodle 4.5 (rúbrica nueva, reemplazo de una existente, de 2 a 5 niveles
por criterio, puntos con decimales y opciones de la rúbrica).

## Instalación (una sola vez)

```bash
pip install -r requirements.txt     # playwright y openpyxl (Excel)
python -m playwright install chromium
```

La interfaz gráfica usa `tkinter`, que viene con Python en Windows y macOS. En Linux
puede requerir instalarlo (p. ej. `sudo apt install python3-tk`).

## Interfaz gráfica

```bash
python gui_importar_rubrica.py
```

1. **Rúbrica:** pulsa «Examinar…» y elige un `.json` o un `.xlsx`. Si es un Excel, se
   convierte automáticamente a un JSON temporal (con `rub_xlsx2json.py`) que se borra al
   terminar; el Excel original no se modifica.
2. **Tarea de Moodle:** URL completa de la tarea (`…/mod/assign/view.php?id=NNN`); el id
   suelto no se admite en la GUI. Si lo dejas vacío, se usa `moodle.url_tarea` de la rúbrica o el
   script lo preguntará.
3. **Opciones** (valores por defecto entre paréntesis):
   - Pedir confirmación antes de guardar o sustituir (**activada**; si se desmarca, equivale a `--sin-revisar`).
   - Sobrescribir la rúbrica si la tarea ya tiene una (**desactivada**, `--reemplazar`).
   - Guardar como borrador (desactivada), forzar nuevo inicio de sesión (desactivada),
     solo validar (desactivada) y navegador (`chromium`, `chrome` o `msedge`).
4. **Vista previa:** al elegir un fichero (o pulsar «Recargar», o entrar en la pestaña),
   la pestaña «Vista previa» muestra la rúbrica como tabla de solo lectura (criterios ×
   niveles, con definiciones y puntos) y un aviso verde «✓ Estructura válida» o rojo con
   los errores encontrados (JSON mal formado, niveles con puntos repetidos,
   `puntuacion_maxima` que no cuadra, escala que no coincide…). Funciona con `.json` y `.xlsx`.
5. **Lotes:** si el fichero es un lote JSON (array de rúbricas, `{"rubricas": [...]}` o el
   maestro `rubricas_ud2.json`), la vista previa muestra todas las rúbricas una bajo otra
   (rueda del ratón, barra de desplazamiento o botones «◀ Anterior / Siguiente ▶»), cada
   una con su propio estado válido/no válido. En un lote:
   - El campo único de URL se desactiva y se activa **«Tareas del lote…»**, un popup con
     una entrada por rúbrica (URL completa; si ya venía en el JSON, aparece rellena). Las rúbricas
     sin URL se omiten al importar.
   - La confirmación antes de guardar queda **siempre activada**.
   - **Importar** exige que todas las rúbricas sean válidas y las importa una tras otra
     (cada una abre y cierra su navegador); contestas a cada confirmación en la pestaña
     «Importar». «Detener» cancela la actual y las pendientes.
6. Pulsa **Importar** (pestaña «Importar»). Se abre el navegador; si no tienes sesión, inicia sesión en Moodle.
   La salida del script aparece en el cuadro «Salida». Cuando el script haga una pregunta
   (confirmar guardado o sustitución, «Pulsa Intro para cerrar el navegador»), contéstala
   con los botones **Sí**, **No**, **Intro** o escribiendo en la línea inferior y pulsando
   «Enviar». Cualquier respuesta que no sea un sí explícito cuenta como NO.
   **Detener** termina el proceso.

La GUI es solo una capa sobre `importar_rubrica.py`: ejecuta el mismo script con los
parámetros equivalentes.

## Rúbricas en Excel

Para editar las rúbricas en Excel, usa la plantilla `templates/plantilla_rubrica.xlsx`
(hay un ejemplo relleno en `ejemplos/rubrica_tarea1.xlsx`). Equivale 1:1 al formato JSON;
las hojas «Instrucciones» y «General» explican cada campo y comprueban los datos.

```bash
# Excel → JSON (sin segundo argumento, crea rubrica.json junto al Excel)
python rub_xlsx2json.py rubrica.xlsx [salida.json]

# JSON → Excel (parte de la plantilla; --plantilla permite usar otra)
python rub_json2xlsx.py rubrica.json [salida.xlsx] [--plantilla RUTA]
```

- `rub_xlsx2json.py` lee las hojas «General» y «Criterios», valida los datos (nombre,
  escala, un nivel por cada nivel de la escala, puntos no repetidos…) y escribe el JSON
  con un bloque `escala`. Si `puntuacion_maxima` no coincide con la suma de máximos,
  solo avisa. Las opciones de Moodle vacías no se incluyen en el JSON.
- `rub_json2xlsx.py` rellena una copia de la plantilla. Si el JSON no trae `escala`, la
  deduce del primer criterio; todos los criterios deben tener el mismo número de niveles
  (máximo 10) y la plantilla admite hasta 300 filas (criterios × niveles). Los niveles
  de cada criterio se ordenan por puntos crecientes.
- Las celdas con fórmulas (marcadas «(automático)») no se editan; se recalculan al abrir el Excel.

## Uso

```bash
# Importar la rúbrica de la Tarea 1 (el script te pedirá la URL de la tarea)
python importar_rubrica.py rubrica_tarea1.json

# Indicando la tarea en la línea de comandos
python importar_rubrica.py rubrica_tarea1.json --url "https://TU-MOODLE/mod/assign/view.php?id=1234"

# O solo con el id de la tarea (el número id=… de su URL)
python importar_rubrica.py rubrica_tarea1.json --moodle https://TU-MOODLE --url 1234

# Sustituir una rúbrica que ya existe (pedirá confirmación antes de sustituirla)
python importar_rubrica.py rubrica_tarea1.json --reemplazar
```

**Por defecto el script es conservador:** sin parámetros, siempre se detiene antes de
guardar para que revises la rúbrica en el navegador y confirmes, y nunca reemplaza una
rúbrica existente (si la tarea ya tiene una, no toca nada). Cualquier respuesta que no
sea un «s» explícito se toma como NO.

Al arrancar se abre el navegador. Si no tienes sesión iniciada, verás la página de
acceso de Moodle: entra con tus datos y el script seguirá solo.

| Opción | Qué hace |
| --- | --- |
| `--url` | URL de la tarea o su id. Si falta, se usa `moodle.url_tarea` del JSON o se pregunta. |
| `--moodle` | URL raíz de Moodle; necesaria si identificas la tarea solo por su id. |
| `--reemplazar` | Permite sustituir una rúbrica existente, tras confirmarlo dos veces (sustituir y guardar). Sin esta opción, una rúbrica existente nunca se toca. |
| `--sin-revisar` | Desactiva las confirmaciones: guarda (y, con `--reemplazar`, sustituye) sin preguntar. Úsalo solo cuando ya confíes en el resultado. |
| `--borrador` | Guarda la rúbrica como borrador en lugar de dejarla lista para usar. |
| `--solo-validar` | Comprueba los JSON sin abrir Moodle. |
| `--navegador chrome` | Usa tu Chrome instalado en lugar del Chromium de Playwright (también `msedge`). |
| `--nueva-sesion` | Ignora la sesión guardada y obliga a iniciar sesión otra vez. |

Se pueden importar varias rúbricas seguidas: `python importar_rubrica.py rubrica_tarea*.json`.
En ese caso, pon la URL de cada tarea en su JSON (`moodle.url_tarea`) o el script la
preguntará una a una.

## Importación en lote

```bash
python importar_lote.py rubricas_ud2.json --moodle https://TU-MOODLE
python importar_lote.py rubricas_ud2.json --tarea 1 --tarea 3     # solo algunas
python importar_lote.py mis_rubricas.json                          # array de rúbricas
```

Acepta un array JSON de rúbricas (o `{"rubricas": [...]}`), el maestro `rubricas_ud2.json`
(`{"tareas": [...]}`, convertido como `generar_json.py`) o una única rúbrica/Excel.
Valida todas antes de empezar y después, **una por una**, usa la URL de su tarea si la
rúbrica la trae en `moodle.url_tarea` (en el maestro `rubricas_ud2.json`, en cada tarea:
`"moodle": {"url_tarea": "https://…/mod/assign/view.php?id=NNN"}`) y **no la pregunta**;
si no la trae (o no es válida), te pide la URL o id (Intro = saltar, `q` = terminar). Lanza `importar_rubrica.py` **siempre con revisión**:
el lote nunca usa `--sin-revisar`, así que debes confirmar cada guardado. Admite
`--moodle`, `--reemplazar`, `--borrador`, `--nueva-sesion`, `--navegador` y `--perfil`.
Al final muestra un resumen con el estado de cada rúbrica.

## Formato del JSON

Esquema completo en `rubrica.schema.json`. Ejemplo mínimo:

```json
{
  "formato_version": 1,
  "nombre": "UD2 · Tarea 1 · Hola Mundo",
  "descripcion": "Texto opcional",
  "puntuacion_maxima": 10,
  "moodle": { "url_tarea": null },
  "opciones": { "mostrar_puntos_alumno": true },
  "criterios": [
    {
      "descripcion": "Compilación y ejecución",
      "niveles": [
        { "nombre": "Insuficiente", "puntos": 0, "definicion": "No compila." },
        { "nombre": "Adecuado",     "puntos": 2, "definicion": "Compila con fallos menores." },
        { "nombre": "Excelente",    "puntos": 4, "definicion": "Todo correcto." }
      ]
    }
  ]
}
```

- Opcionalmente, `escala` (`numero_niveles` y `nombres_niveles`) define una escala común de niveles; la usa la plantilla Excel.
- Cualquier número de criterios y de niveles (mínimo 2 niveles por criterio).
- Los puntos son libres, pero no pueden repetirse dentro de un mismo criterio (Moodle no lo admite).
- `puntuacion_maxima` es opcional: si la pones, el script comprueba que cuadra con la suma.
- `nombre` del nivel es informativo; Moodle solo guarda la definición y los puntos.

## Generar los JSON de la UD2

`rubricas_ud2.json` contiene las 10 rúbricas de la unidad. Para obtener los ficheros
importables:

```bash
python generar_json.py rubricas_ud2.json --tarea 1   # solo la Tarea 1
python generar_json.py rubricas_ud2.json             # las 10
```

## A tener en cuenta

- **Calificación de la tarea.** Moodle escala la puntuación de la rúbrica a la
  calificación máxima de la tarea. Si la tarea está sobre 10 y la rúbrica suma 10,
  coinciden.
- **Sesión.** Mientras siga válida, la sesión se reutiliza entre ejecuciones; se guarda
  en `~/.moodle_rubricas_perfil` (no la compartas). Borra esa carpeta para olvidarla.
- **Si algo falla**, el script guarda una captura `error_<fichero>.png` en la carpeta
  desde la que lo ejecutas. Un tema de Moodle muy personalizado o una versión muy
  distinta puede requerir ajustar algún selector.
- **Sustituir una rúbrica.** Con `--reemplazar` no se borra nada por adelantado: la
  rúbrica existente se sobrescribe en el editor y el cambio solo se aplica al confirmar
  el guardado. Si cancelas, queda como estaba. Evítalo en tareas ya corregidas con esa
  rúbrica: Moodle puede marcar esas calificaciones para revisar.
