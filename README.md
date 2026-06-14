<div align="center">

# specrag

**Catch the reproducibility bugs your LLM forgets between sessions.**

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](#status)
[![Built on PaperQA2](https://img.shields.io/badge/built%20on-PaperQA2-7b42bc.svg)](https://github.com/Future-House/paper-qa)

*A grounded linter that verifies ML code honors the reproducibility norms of papers —
every constraint traceable to a verified verbatim passage.*

</div>

---

## The problem

Ask an LLM to implement a method from a paper twice and you get two different setups. It uses
`batch_size=8` in one session and forgets it in the next. It applies intensity jitter at
**training** time when the paper said **eval only**. These norms live in the model's volatile
parametric memory — so they drift, silently, and your "reproduction" quietly isn't one.

No existing tool catches this. Elicit / Consensus / SciSpace answer *"what does the literature
say?"*; Paper2Code reproduces a paper in code. None answer:

> **Does my generated code honor ALL the reproducibility norms of these papers — consistently —
> with every constraint traceable to a verified passage?**

## What it does

specrag is **not** a retriever (that's commodity — it's built on
[PaperQA2](https://github.com/Future-House/paper-qa)). It's a **grounded linter**:

- **Spec-cards** — typed records of reproducibility constraints, one per `paper × method`, each
  field anchored to a cached **verbatim** passage.
- **`verify`** — a per-field 5-state checklist. **Hard fields** (`batch_size`, `lr`) are compared
  **deterministically**: the LLM only *locates* the value in your code, and code does the
  comparison. Only genuinely **semantic** fields (an augmentation's phase) reach the LLM. No
  holistic judge — that would reproduce the very inconsistency it hunts.
- **Version stamp** — generated code records which card version it was checked against. Re-extract
  the card, change a value, and the old code is flagged **STALE** instead of drifting silently.

### The bug it's built to catch

```python
# paper: "intensity jitter applied only at evaluation"
for x, y in train_loader:
    x = intensity_jitter(x, 0.1)   # <-- applied during TRAINING
```

```text
$ specrag verify card.json train.py
  [BLOCK] intensity_jitter   violated   via llm     <- wrong phase, caught
  BLOCKED (exit 2)
```

## How it works

```
paper PDF ──▶ PaperQA2 substrate ──▶ verbatim passages
                                        │
                     extract (N-way agreement + independent read-back)
                                        ▼
                                  typed spec-card
                                        │
   your ML code ──────────────▶   verify   ──▶  HONORED / VIOLATED / MISSING / AMBIGUOUS
                                        │                                + version stamp
                       moat-critical + unverified card ──▶ escalate to a human
```

A hard verdict never flips between runs (code does the compare). A semantic field is judged by an
LLM, and if it touches a moat-critical, not-yet-human-verified card, a violation **escalates to a
human** instead of auto-blocking — *self-consistent is not the same as verified.*

## Quickstart

```bash
# install (engine + PaperQA2 substrate)
pip install "specrag[paperqa] @ git+https://github.com/RodMed0709/RAG-Research.git"

# bring your own LLM key — DeepSeek by default, any LiteLLM-supported model works
echo "DEEPSEEK_API_KEY=sk-your-own-key" > .env

# verify a code file against a spec-card
specrag verify card.json train.py
```

Exit code: `0` ok · `1` held for human · `2` blocked.

### Inside Claude Code (MCP)

specrag ships an MCP server, so an AI assistant can offload grounded verification to it (the
assistant orchestrates; specrag + your LLM do the grounded check):

```bash
pip install "specrag[mcp] @ git+https://github.com/RodMed0709/RAG-Research.git"
claude mcp add rag-research -- python -m specrag.mcp_server
```

Then just ask: *"use rag-research to verify this code against the card."* Tools exposed:
`verify_code_against_card`, `verify_file_against_card`, `check_code_stamp`.

> **You bring your own LLM key.** specrag never ships one — set `DEEPSEEK_API_KEY` (or configure
> any LiteLLM model). Retrieval runs **fully offline** with local embeddings; only the semantic
> judge/extractor call out.

## Spec-cards

A card is the input you author (by hand, or via the extraction pipeline). Full examples live in
`examples/cards/`. Sketch:

```json
{
  "card_id": "zhou2023thyroid::MedSAM-ft",
  "paper_ref": "zhou2023thyroid", "method": "MedSAM-ft", "version": 1,
  "fields": [
    {
      "name": "batch_size", "category": "hyperparameter",
      "value_kind": "numeric", "locator_kind": "literal",
      "value_spec": {"kind": "numeric", "equals": 8},
      "moat_critical": true,
      "jumper": {
        "pq_dockey": "zhou2023thyroid-pdf",
        "verbatim_text": "...trained with a batch size of 8 per GPU...",
        "anchor_phrase": "batch size of 8", "page_range": "pages 5-6"
      }
    }
  ]
}
```

## Examples

Runnable demos in `examples/` (offline where possible):

| Demo | Shows |
|---|---|
| `run_slice.py` | the 3 verify polarities (block / pass / don't-block) |
| `smoke_substrate.py` | ingest a real PDF, retrieve verbatim passages — offline |
| `smoke_extract.py`, `smoke_llm.py` | extraction + the semantic judge |
| `smoke_full_llm.py` | the full loop: PDF → extract → card → generate → verify → stamp |
| `run_stamp.py` | the version stamp catching cross-session drift |

## Status

Alpha, research tool — **not a maintained product. Use at your own risk.**

**Works today:** verify engine, PaperQA2 substrate (offline retrieval), extraction with N-way
agreement + independent read-back, version stamp, typed card-builder, DeepSeek adapters, CLI, MCP
server. **Not yet:** REST face, image-equation handling, conditional (`applies_when`) verify logic.

## Built on

[PaperQA2](https://github.com/Future-House/paper-qa) (FutureHouse, Apache-2.0) — used as a pip
dependency, not vendored. Please cite *arXiv:2409.13740*. Techniques referenced: Contextual
Retrieval (Anthropic), HyperPIE.

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE). Cite via [CITATION.cff](CITATION.cff).
