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
pip install specrag                 # core: spec-cards + verify (light)
pip install "specrag[paperqa]"      # + PaperQA2 substrate (extraction/retrieval)
pip install "specrag[mcp]"          # + MCP server (use inside Claude Code / agents)
pip install "specrag[all]"
```

## License

Apache-2.0. See `LICENSE`.
