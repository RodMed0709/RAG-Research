---
description: Redacta la sección Methods de un paper directamente desde un repo de código — cada oración anclada a una línea de código verbatim (determinístico). Aspectos que el código no fija se marcan, no se inventan.
argument-hint: <ruta-repo|archivo.py> [titulo] [aspectos-coma-separados]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__RAG-Research__draft_methods_tool, mcp__RAG-Research__draft_methods_from_file
---

# /write-methods — pilar WRITE-from-code

Eres el orquestador. Conviertes un **repo de código ML** en la sección **Methods** de un paper,
donde **cada oración está anclada a una línea de código verbatim**. Es el inverso de specrag:
en vez de verificar que el código honra un paper, escribes el paper desde el código. La garantía
es **determinística**: una oración entra a Methods solo si su valor está literal en el código.

**Argumentos:** `$ARGUMENTS`
- `$1` = ruta al repo o archivo de entrenamiento (`.py`). Obligatorio.
- `$2` = título de la sección (opcional; default "Methods").
- `$3` = aspectos a reportar, coma-separados (opcional; si falta, dedúcelos del código).

## PASO 0 — Reunir el código

1. Si `$1` es un archivo, léelo. Si es un repo, `Glob`/`Read` los archivos de entrenamiento
   relevantes (train*.py, model*.py, config*.py, *.yaml) y concaténalos en un solo dump de
   código (incluye rutas como comentarios para trazabilidad).
2. Deriva los **aspectos** (`$3` o dedúcelos): hiperparámetros (batch_size, lr, epochs,
   optimizer, weight_decay), datos (augmentations + fase, normalización, split), arquitectura
   (backbone, pretrained, loss), entrenamiento (scheduler, early stopping, seed). El conjunto
   de aspectos es parámetro — sirve para cualquier repo.

## PASO 1 — Redactar Methods desde el código (MCP)

Llama `mcp__RAG-Research__draft_methods_tool(aspects, code, title)` con la lista de aspectos y
el dump de código. Por cada aspecto: localiza el valor → lo fija verbatim en una línea →
redacta UNA oración. Devuelve:
- `markdown` — Methods (prosa + apéndice de trazabilidad aspecto→`Lnn: código` + marcadores
  `[SIN EVIDENCIA EN CÓDIGO]` visibles).
- `claims` — por aspecto: value, code_line, lineno, status.
- `no_evidence_count` / `total`.

## PASO 2 — Entregar

1. Escribe `markdown` a `<dir>/<titulo>_methods.md`.
2. Resume: cuántos aspectos quedaron `ANCHORED` vs `SIN EVIDENCIA`. Los `SIN EVIDENCIA` son
   aspectos que el código **no fija explícitamente** — o el paper no debe afirmarlos, o hay que
   buscarlos en config/CLI no incluidos.
3. **No redactes a mano** la oración de un aspecto sin evidencia — rompería la garantía.

## Cierre

Todo número en el Methods sale de una línea real de código (ver trazabilidad). Lo no anclado
está marcado, no inventado. Combina con `/review-consistency` para cruzar Methods vs resultados.
