---
description: Internal-consistency review of a manuscript — numbers, architecture, terminology, sections — with 🔴🟡✍️ severity
argument-hint: <manuscript.pdf|.tex>
allowed-tools: Read, Write, Glob, Grep, mcp__RAG-Research__check_consistency, mcp__RAG-Research__verify_code_against_card
---

# /review-consistency — manuscript internal consistency

You review the manuscript **against itself** (no external literature), combining deterministic
checks (MCP) with judgment over the prose. Manuscript: `$1`.

## 1. Read and extract
Read the manuscript. Extract:
- **Terminology** candidates for inconsistency: group equivalent variants that appear
  (e.g. `["Grad-CAM","GradCAM"]`, acronyms with/without a hyphen).
- **Confusion matrix** (tp/fp/fn/tn) and **reported metrics** (recall/precision/accuracy), if given.
- **Sections present** and the list of **required sections** for the paper type (typically:
  Introduction, Related Work, Methods, Results, Discussion, Conclusion).

## 2. Deterministic checks (MCP)
Call `mcp__RAG-Research__check_consistency(config_json)` with:
```json
{"text": "...", "terminology_groups": [["Grad-CAM","GradCAM"]],
 "confusion": {"tp":11,"fp":2,"fn":4,"tn":100}, "claimed_metrics": {"recall":84.85},
 "sections_present": ["Introduction","Methods"], "sections_required": ["Conclusion"]}
```
Returns findings + `review_md`.

## 3. Semantic checks (judgment)
For what is not deterministic, review it yourself and add 🔴/🟡/✍️ findings:
- **Architecture contradiction** (e.g. a branch described as U-Net in one place, ResNet50 in another).
- **Inconsistent n** (a test-set size that doesn't reconcile across matrix, metrics, and text).
- **Method vs name** (e.g. "TCAV" that is actually K-Means+PCA). If the author's code is available,
  use `verify_code_against_card` with a spec-card of the real method to make the finding objective.
- **Duplicate figures**, internally unsupported claims, over-sold statements.

## 4. Deliver
Merge the deterministic findings (`review_md`) with the semantic ones into `REVIEW.md`, grouped by
severity. Summarize the major 🔴 findings first in chat.
