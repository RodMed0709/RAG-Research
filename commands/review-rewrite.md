---
description: Reescribe/corrige párrafos de un manuscrito con cada frase anclada a evidencia verificada (anti-alucinación), y genera cambios marcados (MD/LaTeX/Word)
argument-hint: <ruta-manuscrito> <corpus-pdfs-dir> [seccion-o-parrafo]
allowed-tools: Read, Write, Edit, Glob, Grep, mcp__RAG-Research__verify_claim_against_corpus, mcp__RAG-Research__render_changes, mcp__RAG-Research__export_docx
---

# /review-rewrite — reescritura verificada de párrafos

Reescribes o corriges prosa del manuscrito `$1` **sin alucinar**: toda afirmación nueva o
reformulada se verifica contra el corpus de PDFs en `$2` antes de quedarse. `$3` = sección o
párrafo objetivo (opcional; si falta, propón los párrafos más débiles).

## Regla dura

No emites ninguna frase con contenido factual que no quede `HONORED` con anchor verbatim.
Lo que salga `UNSUPPORTED`/`CONTRADICTED` → o lo reformulas hasta anclarlo, o lo marcas como
"requiere fuente" y NO lo afirmas.

## Flujo

1. **Leer** el párrafo objetivo + el corpus (`$2`).
2. **Descomponer** el texto (actual o tu reescritura propuesta) en claims atómicos. Construye
   un `ClaimCard` (numeric_fact con value_spec; citation/methodological/novelty/comparative).
3. **Verificar**: `mcp__RAG-Research__verify_claim_against_corpus(claim_card_json, corpus_paths)`.
4. **Reescribir** integrando solo lo `HONORED`, citando la fuente del anchor. Reformula o
   elimina lo `UNSUPPORTED`/`CONTRADICTED`.
5. **Cambios marcados**: por cada edición arma `{before, after, reason, location}` y llama
   `mcp__RAG-Research__render_changes(changes_json)` → `CAMBIOS_MARCADOS.md` + snippet LaTeX.
   - Si el manuscrito es proyecto `.tex` (Overleaf), aplica el markup LaTeX in-place con `Edit`
     (preámbulo: `\usepackage{soul}`, `\usepackage{xcolor}`).
   - Word: `mcp__RAG-Research__export_docx(markdown, out_path)` para `CAMBIOS_MARCADOS.docx`.
6. **Resumen** en chat: nº frases ancladas vs descartadas por falta de evidencia.
