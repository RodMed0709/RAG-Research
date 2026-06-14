# RAG-Research

**Reproducibility-consistency verification for ML code, grounded in papers.**

RAG-Research answers a question existing tools don't: *does my generated code honor ALL the
reproducibility norms of these papers, consistently, with every constraint traceable to a
verified verbatim passage?*

It is a **grounded linter** built on [PaperQA2](https://github.com/Future-House/paper-qa):
typed *spec-cards* (one per `paper × method`, each field anchored to a cached verbatim passage)
plus a per-field 5-state verify. **Hard fields are compared deterministically** (the LLM only
*locates*; code *compares*); only genuinely semantic fields go to the LLM. No holistic judge —
that would reproduce the very inconsistency it hunts.

!!! warning "Status"
    Alpha, research tool — not a maintained product. Use at your own risk.

## How it works

```
paper PDF ──▶ substrate (PaperQA2)  ──▶ verbatim passages
                                         │
                          extraction (N-way + independent read-back)
                                         ▼
                                   typed spec-card  ──┐
                                                      ▼
   your ML code  ─────────────────────────▶  verify_consistency
                                                      │
                          per-field verdict: HONORED / VIOLATED / MISSING / AMBIGUOUS
                          + version stamp (flags stale code across sessions)
```

- **Hard field** (e.g. `batch_size=8`): the LLM locates where it's set in the code; code
  compares against the typed value. Deterministic verdict.
- **Semantic field** (e.g. an augmentation that must run only at eval): the LLM judges. The
  canonical "jitter applied in the wrong phase" bug is caught here.
- **Moat-critical + unverified card**: a violation escalates to a human rather than
  auto-blocking — *self-consistent is not the same as verified*.
- **Version stamp**: generated code records the card version + per-field snapshot; if the card
  is re-extracted and a value (or phase) changes, the old code is flagged STALE.

## Install & use

```bash
pip install "rag-research[paperqa]"     # engine + PaperQA2 substrate
# set DEEPSEEK_API_KEY in a .env file (the LLM is injected; a DeepSeek adapter ships)
rag-research verify card.json train.py
```

## Built on

[PaperQA2](https://github.com/Future-House/paper-qa) (FutureHouse, Apache-2.0) —
cite *arXiv:2409.13740*. Techniques referenced: Contextual Retrieval (Anthropic), HyperPIE.

## License

Apache-2.0.
