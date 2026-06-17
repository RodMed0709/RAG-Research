---
description: Paper-review pipeline — builds the state of the art (search/download/rank the literature) and verifies the manuscript's claims against the corpus (anti-hallucination)
argument-hint: <manuscript.pdf|.tex> [topic] [venue]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__RAG-Research__tier_papers, mcp__RAG-Research__render_report, mcp__RAG-Research__verify_claim_against_corpus
---

# /review-paper — review pillar (state of the art + claim verification)

You are the orchestrator. You build a manuscript's state of the art and verify its claims against
the literature, **without hallucinating**: every statement in the report is anchored to verbatim
text from a source, or marked `UNSUPPORTED`.

**Arguments:** `$ARGUMENTS`
- `$1` = path to the manuscript (`.pdf` or `.tex` project). Required.
- `$2` = topic/domain (optional; infer it from the manuscript if missing).
- `$3` = target venue (optional; conference/journal, for the fit).

The **topic is a parameter**: this pipeline works for any field. Nothing is hardcoded.

## Workspace
Create (if absent) `<manuscript-dir>/state_of_the_art/` with:
```
state_of_the_art/
├── novelty_profile.json     # the paper's novelty axes
├── claims.json              # ClaimCard: assertions to verify
├── fichas/*.json            # one record per paper found
├── pdfs/                    # open-access PDFs downloaded
├── REPORT.md                # full state of the art
└── state_of_the_art_v2.md   # condensed, confidence labels
```

## STEP 0 — Analyze the manuscript
1. Read the manuscript (`Read` for PDF; if `.tex`, read the project's `.tex` files).
2. Derive the **novelty_profile**: decompose the claimed novelty into axes with a role —
   `core` (domain, task, modality), `differentiator` (the distinctive novelty, ≥1 required),
   `context` (dataset, population, region). Write `novelty_profile.json` (NoveltyProfile shape).
3. Derive the **query plan**: 2–4 queries per axis.
4. Extract the verifiable **claims** (numeric, citation, methodological, novelty, comparative).
   Write `claims.json` (ClaimCard shape). `numeric_fact`/`comparative` carry a `value_spec`.

## STEP 1 — Search and download literature (parallel agents)
Launch **N `general-purpose` agents in parallel** (one per axis), in a single message. Each:
- Searches with `WebSearch`/`WebFetch` (Semantic Scholar, arXiv, PubMed/PMC, Google Scholar).
- Downloads **open-access** PDFs to `state_of_the_art/pdfs/`, named `Author_Year_Topic.pdf`.
- For paywalled papers, keeps metadata only (DOI, venue, GitHub if any).
- Returns JSON records: paper_ref, title, authors, year, venue, doi, modalities, is_multimodal,
  xai_techniques, metrics, pdf_status, pdf_path, github_url, **axis_matches**, relation_to_paper.

Write each record to `fichas/<paper_ref>.json`.

## STEP 2 — Rank (deterministic, MCP)
Call `mcp__RAG-Research__tier_papers(profile_json, fichas_json)`. Returns deduped records with
`tier` (T1–T4) and `threat`, sorted by importance.

## STEP 3 — Render the state of the art (MCP)
- `render_report(profile_json, fichas_json, kind="full")` → write `REPORT.md`.
- `render_report(profile_json, fichas_json, kind="v2")` → write `state_of_the_art_v2.md`.

## STEP 4 — Verify claims against the corpus (anti-hallucination, MCP)
Call `verify_claim_against_corpus(claim_card_json, corpus_paths)` with `claims.json` and the PDFs.
Each claim returns `HONORED` (with a verbatim anchor) / `CONTRADICTED` / `UNSUPPORTED` /
`AMBIGUOUS`. Append a **"## Claim verification"** section to `REPORT.md`: a table of
claim · verdict · anchor (verbatim + page) or "no evidence". Flag `UNSUPPORTED`/`CONTRADICTED`
as risks to fix before submitting.

## Close
Summarize in chat: papers per tier, key T1 competitors, uncited T2 twins, and the
`UNSUPPORTED`/`CONTRADICTED` claims. Assert nothing the report does not back with an anchor.

> Next (other commands): `/review-consistency`, `/review-venue`, `/review-rewrite`.
