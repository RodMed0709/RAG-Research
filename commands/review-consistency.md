---
description: Revisión de consistencia interna de un manuscrito — números, arquitectura, terminología, secciones — con severidad 🔴🟡✍️
argument-hint: <ruta-manuscrito.pdf|.tex>
allowed-tools: Read, Write, Glob, Grep, mcp__RAG-Research__check_consistency, mcp__RAG-Research__verify_code_against_card
---

# /review-consistency — consistencia interna del manuscrito

Revisas el manuscrito **contra sí mismo** (sin literatura externa). Combinas chequeos
deterministas (MCP) con juicio sobre prosa. Manuscrito: `$1`.

## 1. Leer y extraer

Lee el manuscrito. Extrae:
- **Terminología** candidata a inconsistencia: agrupa variantes equivalentes que aparezcan
  (ej. `["Grad-CAM","GradCAM"]`, siglas con/sin guion).
- **Matriz de confusión** (tp/fp/fn/tn) y **métricas reportadas** (recall/precision/accuracy),
  si el paper las da.
- **Secciones presentes** y la lista de **secciones obligatorias** del tipo de paper
  (típicas: Introducción, Trabajo Relacionado, Métodos, Resultados, Discusión, Conclusión).

## 2. Chequeos deterministas (MCP)

Llama `mcp__RAG-Research__check_consistency(config_json)` con:
```json
{"text": "...", "terminology_groups": [["Grad-CAM","GradCAM"]],
 "confusion": {"tp":11,"fp":2,"fn":4,"tn":100}, "claimed_metrics": {"recall":84.85},
 "sections_present": ["Introducción","Métodos"], "sections_required": ["Conclusión"]}
```
Devuelve hallazgos + `review_md`.

## 3. Chequeos semánticos (juicio)

Lo que no es determinista, revísalo tú y añádelo como hallazgos 🔴/🟡/✍️:
- **Contradicción de arquitectura** (ej. rama descrita como U-Net en un lugar y ResNet50 en otro).
- **n inconsistente** (n_test que no cuadra entre matriz, métricas y texto).
- **Método vs nombre** (ej. "TCAV" que en realidad es K-Means+PCA). Si hay código del autor,
  usa `verify_code_against_card` con un spec-card del método real para volver objetivo el hallazgo.
- **Figuras duplicadas**, claims sin soporte interno, afirmaciones sobre-vendidas.

## 4. Entregar

Fusiona los hallazgos deterministas (`review_md`) con los semánticos en `REVIEW.md`, agrupados
por severidad. Resume en chat los 🔴 mayores primero.
