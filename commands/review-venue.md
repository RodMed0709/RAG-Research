---
description: Evalúa el fit de un manuscrito con un venue (conferencia/journal) y propone mejoras para aceptación / presentación oral
argument-hint: <ruta-manuscrito.pdf|.tex> <venue>
allowed-tools: Read, Write, Glob, Grep, WebSearch, WebFetch
---

# /review-venue — fit con el venue

Evalúas si el manuscrito `$1` encaja en el venue `$2` y qué falta para que sea aceptado (y,
si aplica, para una buena presentación oral/poster).

## 1. Reglas del venue

Obtén (con `WebSearch`/`WebFetch` si hace falta) las normas del venue `$2`: límite de páginas,
formato (plantilla, ej. CCIS Springer / IEEE), estructura esperada, criterios de revisión,
si es oral/poster, deadlines de cámara lista. Si el venue ya es conocido, usa lo que sabes.

## 2. Evaluar el manuscrito contra esas reglas

Lee el manuscrito y compara:
- **Formato/longitud**: ¿cabe en el límite? ¿plantilla correcta? ¿secciones en el orden esperado?
- **Encaje temático**: ¿el tema/contribución corresponde al scope del venue?
- **Madurez**: ¿resultados suficientes para el estándar del venue? ¿baselines, ablations, n?
- **Presentación** (si oral/poster): qué mensaje de 1 frase vender, qué figura es la "money figure",
  qué simplificar para la charla.

## 3. Entregar `VENUE_FIT.md`

- **Veredicto**: encaje alto/medio/bajo + 1 frase.
- **Bloqueantes** (🔴): lo que impide aceptación tal cual.
- **Mejoras** (🟡): lo que sube probabilidad de aceptación.
- **Para la presentación** (✍️): mensaje central, figura clave, qué recortar.
- **Checklist de formato**: páginas, plantilla, anonimato si doble-ciego, referencias.

Resume en chat el veredicto y los bloqueantes.
