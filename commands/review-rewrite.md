---
description: Rewrite/correct manuscript paragraphs with every sentence anchored to verified evidence (anti-hallucination), and produce tracked changes (MD/LaTeX/Word)
argument-hint: <manuscript> <corpus-pdfs-dir> [section-or-paragraph]
allowed-tools: Read, Write, Edit, Glob, Grep, mcp__RAG-Research__verify_claim_against_corpus, mcp__RAG-Research__render_changes, mcp__RAG-Research__export_docx
---

# /review-rewrite — verified paragraph rewriting

You rewrite or correct prose in manuscript `$1` **without hallucinating**: every new or reworded
factual statement is verified against the corpus of PDFs in `$2` before it stays. `$3` = target
section or paragraph (optional; if absent, propose the weakest paragraphs).

## Hard rule
You emit no sentence with factual content unless it is `HONORED` with a verbatim anchor. Anything
`UNSUPPORTED`/`CONTRADICTED` → either reword it until it anchors, or mark it "needs a source" and
do NOT assert it.

## Flow
1. **Read** the target paragraph + the corpus (`$2`).
2. **Decompose** the text (current or your proposed rewrite) into atomic claims. Build a
   `ClaimCard` (numeric_fact with value_spec; citation/methodological/novelty/comparative).
3. **Verify**: `verify_claim_against_corpus(claim_card_json, corpus_paths)`.
4. **Rewrite** integrating only the `HONORED` claims, citing the anchor's source. Reword or drop
   the `UNSUPPORTED`/`CONTRADICTED` ones.
5. **Tracked changes**: for each edit build `{before, after, reason, location}` and call
   `render_changes(changes_json)` → `TRACKED_CHANGES.md` + a LaTeX snippet.
   - For a `.tex` project (Overleaf), apply the LaTeX markup in place with `Edit` (preamble:
     `\usepackage{soul}`, `\usepackage{xcolor}`).
   - For Word: `export_docx(markdown, out_path)` → `TRACKED_CHANGES.docx`.
6. **Summary** in chat: number of sentences anchored vs dropped for lack of evidence.
