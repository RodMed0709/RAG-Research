# specrag

**Reproducibility-consistency verification for ML code, grounded in papers.**

specrag answers a question existing tools don't: *"does my generated code honor ALL the
reproducibility norms of these papers, consistently, with every constraint traceable to a
verified verbatim passage?"*

It is **not** a retriever (that's commodity). It is a **grounded linter**: typed *spec-cards*
(one per `paper × method`, each field anchored to a cached verbatim passage) plus
`verify_consistency` — a per-field 5-state checklist where **hard fields are compared
deterministically** (the LLM only *locates*, code *compares*) and the LLM judges only
genuinely semantic fields. No holistic judge — that would reproduce the very bug it hunts.

> **Status: alpha, research tool — not a maintained product. Use at your own risk.**

## Built on

specrag is built on **[PaperQA2](https://github.com/Future-House/paper-qa)** (FutureHouse,
Apache-2.0), used as a pip dependency for parsing, chunking, retrieval and citations.
Cite: *arXiv:2409.13740*. See `NOTICE`.

## Install

```bash
pip install specrag                 # core: spec-cards + verify + version stamp (light)
pip install "specrag[paperqa]"      # + PaperQA2 substrate (PDF ingest, retrieval)
```

The engine takes the LLM as an injected callable. `specrag.llm` ships a DeepSeek adapter
(via LiteLLM); set `DEEPSEEK_API_KEY` in a `.env` file. An MCP server and a REST face are
planned, not yet implemented.

## Usage

Verify a code file against a (hand-authored or extracted) spec-card, using DeepSeek as the
semantic judge and code-value locator:

```bash
specrag verify card.json train.py
```

Per-field verdicts print with a `BLOCK` / `HUMAN` / `ok` marker; exit code is `0` (ok),
`1` (held for human), or `2` (blocked). Hard fields are compared deterministically; only
semantic fields go to the LLM. See `examples/` for runnable demos (`run_slice.py`,
`smoke_substrate.py`, `smoke_extract.py`, `smoke_llm.py`, `run_stamp.py`).

## Status

Working today: the verify engine (5-state per-field checklist, deterministic hard-field
compare, moat-critical human-escalation), the PaperQA2 substrate (offline local-embedding
retrieval), card extraction with N-way agreement + independent read-back, the version stamp,
the typed card-builder, real DeepSeek adapters, and a CLI. Not yet: MCP/REST faces, image
equation handling, conditional (`applies_when`) verify logic.

## License

Apache-2.0. See `LICENSE`.
