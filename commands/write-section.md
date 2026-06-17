---
description: Redacta una sección de paper desde un outline de bullets, con cada oración anclada a evidencia verbatim del corpus (anti-alucinación). Bullets sin soporte se marcan, no se inventan.
argument-hint: <outline.md|.txt> [titulo-seccion] [carpeta-corpus]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__RAG-Research__draft_section_tool
---

# /write-section — pilar WRITE-from-papers

Eres el orquestador. Conviertes un **outline de bullets** en prosa de paper donde **cada
oración nace anclada a un pasaje verbatim** del corpus. Si un bullet no tiene soporte, se
marca `SIN EVIDENCIA` — **nunca se inventa**. Es el inverso de `/review-paper`: en vez de
verificar claims existentes, generas claims nuevas que ya nacen verificadas.

**Argumentos:** `$ARGUMENTS`
- `$1` = ruta a un outline (`.md`/`.txt`), un bullet por línea. Obligatorio.
- `$2` = título de la sección (opcional; ej. "Related Work", "Background"). Default: "Section".
- `$3` = carpeta del corpus (opcional; PDFs fuente). Default: `<dir-del-outline>/pdfs/`.

El tema es parámetro: sirve para cualquier campo. Nada hardcodeado.

## PASO 0 — Preparar entradas

1. Lee el outline (`Read`). Cada línea no vacía (quita `-`/`*`/numeración) = un bullet.
2. Localiza el corpus: `$3` o `<dir-del-outline>/pdfs/`. Si no hay PDFs, díselo al usuario y
   ofrece correr primero la fase de adquisición de literatura de `/review-paper` (PASO 1).

## PASO 1 — Redactar la sección anclada (MCP)

Llama `mcp__RAG-Research__draft_section_tool(outline, corpus_paths, title, k)` con:
- `outline` = lista de bullets.
- `corpus_paths` = lista de rutas de PDFs del corpus.
- `title` = `$2`.

Por cada bullet la tool: recupera pasajes verbatim → redacta UNA oración sólo desde esos
pasajes → **re-verifica con el motor anti-alucinación** (`verify_claim`). La oración entra a
la prosa sólo si gana un anchor verbatim (`ANCHORED`). Devuelve:
- `markdown` — la sección renderizada (prosa con citas + marcadores `SIN EVIDENCIA` visibles +
  apéndice de trazabilidad bullet→verbatim).
- `cards` — una draft-card por bullet (status, anchor, source).
- `no_evidence_count` / `total`.

## PASO 2 — Entregar

1. Escribe `markdown` a `<dir-del-outline>/<titulo>_draft.md`.
2. Resume en chat: cuántas oraciones quedaron `ANCHORED`, cuántas `SIN EVIDENCIA`, y qué
   bullets faltan de soporte (son los huecos a investigar o a recortar del paper).
3. Para los `SIN EVIDENCIA`: ofrece ampliar el corpus (más PDFs) o reformular el bullet. **No
   redactes tú a mano la oración faltante** — rompería la garantía anti-alucinación.

## Cierre

No afirmes nada que la tool no haya anclado. Los marcadores `SIN EVIDENCIA` son una feature,
no un bug: son exactamente las afirmaciones que el corpus no respalda.

> Después: `/review-consistency` sobre el draft, entrega Word/LaTeX con `render_changes`/`export_docx`.
