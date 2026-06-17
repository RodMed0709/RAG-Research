---
description: Draft a paper's Methods section straight from a code repo — every sentence anchored to a verbatim code line (deterministic). Aspects the code does not set are flagged, not invented.
argument-hint: <repo|file.py> [title] [comma-separated-aspects]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__RAG-Research__draft_methods_tool, mcp__RAG-Research__draft_methods_from_file
---

# /write-methods — anchored drafting (from code)

You are the orchestrator. You turn an **ML code repo** into a paper's **Methods** section, where
**every sentence is anchored to a verbatim code line**. It is the inverse of the code↔paper check:
instead of verifying that code honors a paper, you write the paper from the code. The guarantee is
**deterministic**: a sentence enters Methods only if its value appears literally in the code.

**Arguments:** `$ARGUMENTS`
- `$1` = path to the repo or training file (`.py`). Required.
- `$2` = section title (optional; default "Methods").
- `$3` = aspects to report, comma-separated (optional; infer them from the code if absent).

## STEP 0 — Gather the code
1. If `$1` is a file, read it. If it's a repo, `Glob`/`Read` the relevant training files
   (train*.py, model*.py, config*.py, *.yaml) and concatenate them into one code dump (include
   paths as comments for traceability).
2. Derive the **aspects** (`$3` or infer): hyperparameters (batch_size, lr, epochs, optimizer,
   weight_decay), data (augmentations + phase, normalization, split), architecture (backbone,
   pretrained, loss), training (scheduler, early stopping, seed). The aspect set is a parameter —
   it works for any repo.

## STEP 1 — Draft Methods from the code (MCP)
Call `mcp__RAG-Research__draft_methods_tool(aspects, code, title)`. For each aspect it locates the
value → pins it verbatim to a line → drafts ONE sentence. Returns:
- `markdown` — Methods (prose + traceability appendix aspect→`Lnn: code` + visible
  `[NOT IN CODE]` markers).
- `claims` — per aspect: value, code_line, lineno, status.
- `no_evidence_count` / `total`.

## STEP 2 — Deliver
1. Write `markdown` to `<dir>/<title>_methods.md`.
2. Summarize: how many aspects are `ANCHORED` vs `[NOT IN CODE]`. The `[NOT IN CODE]` ones are
   aspects the code does not set explicitly — either the paper should not assert them, or they
   live in a config/CLI not included.
3. **Do not hand-write** the sentence for an unsupported aspect — it would break the guarantee.

## Close
Every number in Methods comes from a real code line (see traceability). What is not anchored is
flagged, not invented. Combine with `/review-consistency` to cross-check Methods against Results.
