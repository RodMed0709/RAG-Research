---
description: Pipeline de revisión de paper — estado del arte (busca/baja/rankea literatura) + verificación anti-alucinación de claims contra el corpus
argument-hint: <ruta-manuscrito.pdf|.tex> [tema] [venue]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__RAG-Research__tier_papers, mcp__RAG-Research__render_report, mcp__RAG-Research__verify_claim_against_corpus
---

# /review-paper — pilar de revisión (estado del arte + verificación de claims)

Eres el orquestador. Construyes el estado del arte de un manuscrito y verificas sus
afirmaciones contra la literatura, **sin alucinar**: toda afirmación del reporte se ancla a
texto verbatim de una fuente, o se marca `UNSUPPORTED`.

**Argumentos:** `$ARGUMENTS`
- `$1` = ruta al manuscrito (`.pdf` o proyecto `.tex`). Obligatorio.
- `$2` = tema/dominio (opcional; si falta, dedúcelo del manuscrito). Ej: segmentación, dMRI, DTI.
- `$3` = venue objetivo (opcional; conferencia/journal para el fit).

El **tema es parámetro**: este pipeline sirve para cualquier campo. Nada hardcodeado.

## Workspace

Crea (si no existe) `<dir-del-manuscrito>/estado_del_arte/` con:
```
estado_del_arte/
├── novelty_profile.json     # ejes de novedad del paper
├── claims.json              # ClaimCard: afirmaciones a verificar
├── fichas/*.json            # una ficha por paper hallado
├── pdfs/                    # PDFs open-access descargados
├── REPORTE.md               # estado del arte completo
└── estado_del_arte_v2.md    # condensado, etiquetas de confianza
```

## PASO 0 — Analizar el manuscrito

1. Lee el manuscrito (`Read` para PDF; si es `.tex`, lee los `.tex` del proyecto).
2. Deriva el **novelty_profile**: descompón la novedad declarada en ejes con rol:
   - `core` — espacio del paper (dominio, tarea, modalidad).
   - `differentiator` — lo raro que vende como novedad (≥1 obligatorio).
   - `context` — dataset, población, región.
   Escribe `novelty_profile.json` con el shape de `NoveltyProfile` (paper_ref, axes[{name,description,role}]).
3. Deriva el **query_plan**: 2-4 queries por eje, combinando términos (ej. "<dominio> <técnica>",
   "<dominio> <modalidad> fusion", "<técnica> <dominio>", geográficas para `context`).
4. Extrae los **claims** verificables (numéricos, de cita, metodológicos, de novedad,
   comparativos). Escribe `claims.json` con shape `ClaimCard` (card_id, manuscript_ref,
   claims[{claim_id, text, kind, value_spec?, location}]). Los `numeric_fact`/`comparative`
   llevan `value_spec` (kind numeric/range + equals/low/high).

## PASO 1 — Buscar y bajar literatura (agentes paralelos)

Lanza **N agentes `general-purpose` en paralelo** (uno por eje/dimensión del query_plan), en
un solo mensaje con varios `Agent`. Cada agente:
- Busca con `WebSearch` y `WebFetch` en Semantic Scholar, arXiv, PubMed/PMC, Google Scholar,
  SciELO (este último para Latinoamérica).
- Descarga los PDF **open-access** a `estado_del_arte/pdfs/`, nombrando `Author_Year_Topic.pdf`.
- Para los de paywall, guarda solo metadata (DOI, venue, GitHub si hay).
- Devuelve una lista de fichas JSON con: paper_ref, title, authors, year, venue, doi, arxiv,
  modalities, is_multimodal, xai_techniques, metrics, pdf_status (local|paywall|unavailable),
  pdf_path, github_url, **axis_matches** (dict eje→bool: ¿este paper toca ese eje del profile?),
  relation_to_paper (1 frase).
- El juicio semántico (¿toca el eje?) lo hace el agente al crear la ficha; el tiering luego es
  determinista.

Reúne todas las fichas, escribe cada una en `fichas/<paper_ref>.json`.

## PASO 2 — Rankear (determinista, MCP)

Llama `mcp__RAG-Research__tier_papers(profile_json, fichas_json)` con el novelty_profile y el
array de fichas. Devuelve fichas dedupeadas, con `tier` (T1-T4) y `threat`, ordenadas por
importancia. Guarda el resultado.

## PASO 3 — Renderizar el estado del arte (MCP)

- `mcp__RAG-Research__render_report(profile_json, fichas_json, kind="full")` → escribe `REPORTE.md`.
- `mcp__RAG-Research__render_report(profile_json, fichas_json, kind="v2")` → escribe `estado_del_arte_v2.md`.

## PASO 4 — Verificar claims contra el corpus (anti-alucinación, MCP)

Llama `mcp__RAG-Research__verify_claim_against_corpus(claim_card_json, corpus_paths)` con
`claims.json` y la lista de PDFs en `estado_del_arte/pdfs/`. Por cada claim devuelve
`HONORED` (con anchor verbatim) / `CONTRADICTED` / `UNSUPPORTED` / `AMBIGUOUS`.

Anexa a `REPORTE.md` una sección **"## 5. Verificación de afirmaciones"**:
- Tabla: claim · veredicto · anchor (verbatim + página) o "sin evidencia".
- Resalta los `UNSUPPORTED`/`CONTRADICTED` como riesgos a corregir antes de enviar.

## Cierre

Resume en chat: nº papers por tier, competidores T1 clave, gemelos T2 no citados, claims
`UNSUPPORTED`/`CONTRADICTED`. No afirmes nada sin que el reporte lo respalde con anchor.

> Fases siguientes (otros comandos): `/review-consistency` (consistencia interna),
> `/review-venue` (fit conferencia/journal), entrega Word/LaTeX.
