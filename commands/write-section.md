---
description: Draft a paper section from an outline of bullets, every sentence anchored to a verbatim passage from the corpus (anti-hallucination). Unsupported bullets are flagged, not invented.
argument-hint: <outline.md|.txt> [section-title] [corpus-dir]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__RAG-Research__draft_section_tool
---

# /write-section — anchored drafting (from papers)

You are the orchestrator. You turn an **outline of bullets** into paper prose where **every
sentence is born anchored to a verbatim passage** from the corpus. If a bullet has no support, it
is marked `[NO EVIDENCE]` — **never invented**. It is the inverse of `/review-paper`: instead of
verifying existing claims, you generate new claims that are already verified.

**Arguments:** `$ARGUMENTS`
- `$1` = path to an outline (`.md`/`.txt`), one bullet per line. Required.
- `$2` = section title (optional; e.g. "Related Work", "Background"). Default: "Section".
- `$3` = corpus directory (optional; source PDFs). Default: `<outline-dir>/pdfs/`.

The topic is a parameter: this works for any field. Nothing is hardcoded.

## STEP 0 — Prepare inputs
1. Read the outline (`Read`). Each non-empty line (strip `-`/`*`/numbering) = one bullet.
2. Locate the corpus: `$3` or `<outline-dir>/pdfs/`. If there are no PDFs, tell the user and offer
   to run the literature-acquisition phase of `/review-paper` (STEP 1) first.

## STEP 1 — Draft the anchored section (MCP)
Call `mcp__RAG-Research__draft_section_tool(outline, corpus_paths, title, k)`. For each bullet the
tool retrieves verbatim passages → drafts ONE sentence from those passages only → **re-verifies
with the anti-hallucination engine** (`verify_claim`). The sentence enters the prose only if it
earns a verbatim anchor (`ANCHORED`). It returns:
- `markdown` — the rendered section (prose with citations + visible `[NO EVIDENCE]` markers + a
  traceability appendix bullet→verbatim).
- `cards` — one draft-card per bullet (status, anchor, source).
- `no_evidence_count` / `total`.

## STEP 2 — Deliver
1. Write `markdown` to `<outline-dir>/<title>_draft.md`.
2. Summarize in chat: how many sentences are `ANCHORED`, how many `[NO EVIDENCE]`, and which
   bullets lack support (the gaps to research or to cut from the paper).
3. For the `[NO EVIDENCE]` ones: offer to expand the corpus (more PDFs) or reword the bullet. **Do
   not hand-write the missing sentence yourself** — it would break the anti-hallucination guarantee.

## Close
Assert nothing the tool did not anchor. The `[NO EVIDENCE]` markers are a feature, not a bug: they
are exactly the statements the corpus does not support.

> Next: `/review-consistency` on the draft; deliver Word/LaTeX with `render_changes`/`export_docx`.
