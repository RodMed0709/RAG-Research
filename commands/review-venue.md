---
description: Assess a manuscript's fit with a venue (conference/journal) and propose improvements for acceptance / oral presentation
argument-hint: <manuscript.pdf|.tex> <venue>
allowed-tools: Read, Write, Glob, Grep, WebSearch, WebFetch
---

# /review-venue — venue fit

You assess whether manuscript `$1` fits venue `$2`, and what is missing for it to be accepted (and,
where relevant, to present well as an oral/poster).

## 1. Venue rules
Obtain (with `WebSearch`/`WebFetch` if needed) the venue's rules: page limit, format (template,
e.g. CCIS Springer / IEEE), expected structure, review criteria, oral/poster, camera-ready
deadlines. If the venue is well known, use what you know.

## 2. Evaluate the manuscript against those rules
Read the manuscript and compare:
- **Format/length**: within the limit? correct template? sections in the expected order?
- **Topical fit**: does the topic/contribution match the venue's scope?
- **Maturity**: enough results for the venue's bar? baselines, ablations, n?
- **Presentation** (if oral/poster): the one-sentence message to sell, the "money figure", what to
  simplify for the talk.

## 3. Deliver `VENUE_FIT.md`
- **Verdict**: high/medium/low fit + one sentence.
- **Blockers** (🔴): what prevents acceptance as-is.
- **Improvements** (🟡): what raises the acceptance odds.
- **For the talk** (✍️): core message, key figure, what to cut.
- **Format checklist**: pages, template, anonymity if double-blind, references.

Summarize the verdict and blockers in chat.
