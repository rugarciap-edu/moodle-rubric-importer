---
name: generar-rubrica-moodle
description: Genera rúbricas de evaluación en el formato JSON (formato_version 1) del proyecto moodle-rubric-importer, listas para importar en Moodle con importar_rubrica.py o importar_lote.py. Úsala cuando el usuario pida crear, diseñar o convertir una rúbrica (de una tarea, enunciado, práctica o criterios en texto) a JSON para Moodle.
---

# Generar rúbricas JSON para Moodle

Produce un fichero `.json` válido según [references/rubrica.schema.json](references/rubrica.schema.json). Ejemplo completo: [references/ejemplo_rubrica_tarea1.json](references/ejemplo_rubrica_tarea1.json).

## Flujo

1. Reúne lo necesario a partir del enunciado o los criterios del usuario: nombre de la tarea, puntuación total, criterios y pesos. Si falta algo importante (puntuación total, nº de niveles), pregunta; si no, aplica los valores por defecto de abajo y dilo.
2. Diseña los criterios: cada uno evalúa un aspecto observable y distinto, sin solapes.
3. Escribe una `definicion` concreta y verificable para cada nivel (qué hace el alumno), no adjetivos vagos. El nivel máximo describe todo lo esperado; los inferiores indican qué falta.
4. Reparte los puntos y valida las reglas de abajo antes de entregar.
5. Entrega el JSON en un fichero (p. ej. `rubrica_<tarea>.json`, UTF-8) o en un bloque ```json, sin comentarios dentro del JSON.

## Estructura

```json
{
  "formato_version": 1,
  "nombre": "...",
  "descripcion": "...",
  "puntuacion_maxima": 10,
  "escala": { "numero_niveles": 3, "nombres_niveles": ["Insuficiente", "Adecuado", "Excelente"] },
  "moodle": { "url_tarea": null },
  "opciones": { "ordenar_niveles_ascendente": true, "mostrar_descripcion_alumno": true,
                "mostrar_puntos_alumno": true, "permitir_comentarios": true,
                "mostrar_comentarios_alumno": true },
  "criterios": [
    { "descripcion": "...", "niveles": [ { "nombre": "...", "puntos": 0, "definicion": "..." } ] }
  ]
}
```

## Reglas obligatorias (el importador falla si no se cumplen)

- `formato_version` es exactamente `1`; `nombre` no vacío; `criterios` con ≥ 1 elemento.
- Cada criterio: `descripcion` y `niveles` (≥ 2 niveles).
- Cada nivel: `puntos` (número ≥ 0) y `definicion` no vacía. `nombre` es opcional (informativo).
- Dentro de un criterio los `puntos` NO pueden repetirse.
- Si se pone `puntuacion_maxima`, debe ser igual a la suma de los puntos máximos de cada criterio. Calcula la suma.
- Si se pone `escala` (la usa la plantilla Excel), todos los criterios deben tener exactamente `numero_niveles` niveles (2–10) y el `nombre` de cada nivel, en orden, igual a `nombres_niveles`.
- `opciones` solo admite estas claves booleanas (cualquier otra da error): `ordenar_niveles_ascendente`, `bloquear_cero_puntos`, `mostrar_definicion_siempre`, `mostrar_descripcion_profesor`, `mostrar_descripcion_alumno`, `mostrar_puntos_profesor`, `mostrar_puntos_alumno`, `permitir_comentarios`, `mostrar_comentarios_alumno`.
- `moodle.url_tarea`: `null` salvo que el usuario dé la URL (`…/mod/assign/view.php?id=NNN`).

## Valores por defecto (si el usuario no indica otra cosa)

- 3 niveles: Insuficiente / Adecuado / Excelente, con `escala` incluida; niveles de menor a mayor puntuación (0, mitad, máximo).
- Puntuación total 10; opciones como en el ejemplo; `url_tarea: null`.
- Idioma del contenido: el del usuario (normalmente español).

## Varias rúbricas (lote)

`importar_lote.py` acepta una lista JSON de rúbricas o un objeto `{"rubricas": [ ... ]}`, cada elemento con la estructura anterior. Úsalo si se piden varias.

## Comprobación final

JSON bien formado (sin comas finales), puntos sin duplicados por criterio, suma = `puntuacion_maxima`, niveles coherentes con `escala`. Indica cómo importarla:

```
python importar_rubrica.py rubrica_<tarea>.json --moodle https://TU-MOODLE
```
