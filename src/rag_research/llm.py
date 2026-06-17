"""Real LLM adapters (DeepSeek via LiteLLM) for the engine's injected interfaces.

The core takes callables (Judge, Locator, Extractor, ReadBack, Generator) so it stays
model-agnostic; this module is ONE concrete source of them. Needs ``litellm`` (present via
the ``[paperqa]`` extra) and ``DEEPSEEK_API_KEY`` in the environment. Keeping the model here
means no test or core import depends on a network call — they inject fakes instead.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from .claim import ClaimVerdict
from .claimverify import ClaimExtractor, ClaimJudge
from .codegen import Generator
from .codewrite import CodeValueLocator, CodeWriter
from .draft import Writer
from .extract import Extractor, ReadBack
from .speccard import SpecCard, SpecField, State
from .verify import Judge, Locator

DEEPSEEK = "deepseek/deepseek-chat"
_STATE_BY_NAME = {s.name: s for s in State}
_VERDICT_BY_NAME = {v.name: v for v in ClaimVerdict}


def load_env(path: str | os.PathLike[str] = ".env") -> None:
    """Minimal .env loader (no python-dotenv dependency). Does not overwrite existing vars."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def _complete(
    system: str, user: str, *, model: str, max_tokens: int = 64,
    temperature: float = 0.0, timeout: float = 30.0,
) -> str:
    import litellm  # lazy: only imported when a real adapter actually runs

    resp = litellm.completion(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    return (resp.choices[0].message.content or "").strip()


def _field_brief(field: SpecField) -> str:
    vs = field.value_spec
    parts = [f"name={field.name}", f"value_kind={field.value_kind.value}"]
    if vs.equals is not None:
        parts.append(f"expected={vs.equals!r}")
    if vs.aliases:
        parts.append(f"aliases={vs.aliases}")
    if vs.low is not None or vs.high is not None:
        parts.append(f"range=[{vs.low},{vs.high}]")
    if field.phase is not None:
        parts.append(f"phase={field.phase.value}")
    if field.unit:
        parts.append(f"unit={field.unit}")
    return ", ".join(parts)


def _clean_value(out: str) -> str | None:
    # strip the WHOLE reply, not .split()[0] — keep multi-word values ("zero mean unit variance")
    s = out.strip().strip(" .,;:'\"`")
    if not s or s.upper().startswith("NONE"):
        return None
    return s


def _parse_state(text: str) -> State:
    """Map an LLM reply to a State, failing SAFE. Exact match wins; otherwise a single
    word-boundary state token wins; zero or MULTIPLE distinct tokens -> AMBIGUOUS (human
    queue). This refuses to read 'HONORED but actually VIOLATED' as HONORED."""
    up = text.strip().upper().strip(".")
    if up in _STATE_BY_NAME:
        return _STATE_BY_NAME[up]
    hits = {st for name, st in _STATE_BY_NAME.items() if re.search(rf"\b{name}\b", up)}
    return next(iter(hits)) if len(hits) == 1 else State.AMBIGUOUS


def make_judge(model: str = DEEPSEEK) -> Judge:
    def judge(field: SpecField, code: str) -> State:
        system = (
            "You check whether ML code honors ONE reproducibility constraint. Reply with exactly "
            "one word:\n"
            "HONORED = the code does what the constraint requires.\n"
            "VIOLATED = the code does the opposite (wrong value, or wrong phase).\n"
            "MISSING = the constraint's subject does not appear in the code.\n"
            "NOT_APPLICABLE / AMBIGUOUS only if truly so.\n"
            "PHASE RULE: if the constraint's required phase is 'eval', the augmentation must run "
            "ONLY when evaluating. Running it ONLY inside an eval branch = HONORED. Running it in "
            "the training loop = VIOLATED."
        )
        phase = f" only in the '{field.phase.value}' phase" if field.phase is not None else ""
        expected = field.value_spec.equals
        user = (
            f"Constraint: apply '{field.name}'{phase}."
            + (f" Expected value: {expected!r}." if expected is not None else "")
            + f"\n\nCode:\n```\n{code}\n```\n\nVerdict (one word):"
        )
        return _parse_state(_complete(system, user, model=model, max_tokens=8))

    return judge


def make_extractor(model: str = DEEPSEEK) -> Extractor:
    def extractor(passage_text: str, field_name: str) -> str | None:
        system = (
            "You extract a single reproducibility value from an ML paper passage. Output ONLY "
            "the value (e.g. 8, 1e-4, z-score), or the word NONE if the passage does not state it."
        )
        user = f"Field: {field_name}\n\nPassage:\n{passage_text}\n\nValue:"
        return _clean_value(_complete(system, user, model=model, max_tokens=16))

    return extractor


def make_reader(model: str = DEEPSEEK) -> ReadBack:
    # Deliberately different framing than the extractor; pair with a distinct reader_id at the
    # call site so the independence check in extract_field is real.
    def reader(verbatim: str, field_name: str) -> str | None:
        system = (
            "Read the passage and report the value the authors state for the named field. "
            "Output ONLY the value, or NONE if it is not stated here."
        )
        user = f"What value does this text give for '{field_name}'?\n\n{verbatim}\n\nValue:"
        return _clean_value(_complete(system, user, model=model, max_tokens=16))

    return reader


def make_locator(model: str = DEEPSEEK) -> Locator:
    def locator(field: SpecField, code: str) -> str | None:
        system = (
            "Find where the named field is configured in the code and report ONLY its literal "
            "value as a bare number or string (normalized, no units), or NONE if absent."
        )
        user = f"Field: {field.name}\n\nCode:\n```\n{code}\n```\n\nLiteral value:"
        return _clean_value(_complete(system, user, model=model, max_tokens=16))

    return locator


def _parse_verdict(text: str) -> ClaimVerdict:
    """Map an LLM reply to a ClaimVerdict, failing SAFE to AMBIGUOUS (human queue). Exact
    match wins; else a single word-boundary token wins; zero or multiple -> AMBIGUOUS."""
    up = text.strip().upper().strip(".")
    if up in _VERDICT_BY_NAME:
        return _VERDICT_BY_NAME[up]
    # A negated reply ("NOT HONORED") would single-token-match HONORED; fail SAFE instead.
    if re.search(r"\b(NOT|NO|N'T)\b", up):
        return ClaimVerdict.AMBIGUOUS
    hits = {v for name, v in _VERDICT_BY_NAME.items() if re.search(rf"\b{name}\b", up)}
    return next(iter(hits)) if len(hits) == 1 else ClaimVerdict.AMBIGUOUS


def _passages_block(passage_texts: list[str], *, limit: int = 6) -> str:
    return "\n\n".join(f"[P{i + 1}] {t}" for i, t in enumerate(passage_texts[:limit]))


def make_claim_judge(model: str = DEEPSEEK) -> ClaimJudge:
    """Judge a freeform manuscript claim against retrieved source passages. The verdict is
    grounded ONLY in the passages — no outside knowledge — so an unsupported claim cannot be
    rescued by the model's priors (that is the anti-hallucination point)."""
    def judge(claim_text: str, passage_texts: list[str]) -> ClaimVerdict:
        system = (
            "You verify ONE claim from a paper against retrieved source passages. Use ONLY the "
            "passages, never outside knowledge. Reply with exactly one word:\n"
            "HONORED = a passage clearly supports the claim.\n"
            "CONTRADICTED = a passage clearly states the opposite.\n"
            "UNSUPPORTED = the passages do not address the claim (do NOT guess from priors).\n"
            "AMBIGUOUS = passages are mixed or unclear."
        )
        user = (
            f"Claim:\n{claim_text}\n\nSource passages:\n{_passages_block(passage_texts)}"
            "\n\nVerdict (one word):"
        )
        return _parse_verdict(_complete(system, user, model=model, max_tokens=8))

    return judge


def make_claim_extractor(model: str = DEEPSEEK) -> ClaimExtractor:
    """Extract, from the passages, the value the SOURCES report for a numeric/comparative
    claim — so a deterministic compare can decide it. Returns the bare value or None."""
    def extractor(claim_text: str, passage_texts: list[str]) -> str | None:
        system = (
            "From the source passages, output ONLY the numeric value (or enum value) the "
            "SOURCES report for the quantity in the claim — a bare number/string, normalized, "
            "no units. Output NONE if the passages do not state it. Use ONLY the passages."
        )
        user = (
            f"Claim:\n{claim_text}\n\nSource passages:\n{_passages_block(passage_texts)}"
            "\n\nReported value:"
        )
        return _clean_value(_complete(system, user, model=model, max_tokens=16))

    return extractor


def make_writer(model: str = DEEPSEEK) -> Writer:
    """Write ONE prose sentence for an outline bullet, grounded ONLY in the retrieved
    passages — no outside knowledge. The output is a CANDIDATE: ``draft_bullet`` re-verifies
    it with ``verify_claim`` before letting it into the prose, so a sentence that strays
    beyond the passages is caught and downgraded to NO_EVIDENCE."""
    def writer(bullet: str, passage_texts: list[str]) -> str:
        system = (
            "You are drafting one sentence of a paper. Write a SINGLE declarative sentence that "
            "states the point of the bullet USING ONLY the facts in the source passages. Never "
            "add numbers, names, or claims absent from the passages. If the passages do not "
            "support the bullet, write the most cautious sentence the passages allow. Output "
            "ONLY the sentence, no prose around it."
        )
        user = (
            f"Bullet:\n{bullet}\n\nSource passages:\n{_passages_block(passage_texts)}"
            "\n\nSentence:"
        )
        return _complete(system, user, model=model, max_tokens=120)

    return writer


def make_code_locator(model: str = DEEPSEEK) -> CodeValueLocator:
    """Locate the literal value of a named aspect inside a code repo dump. Returns the bare
    value (so codewrite can pin it verbatim) or None. WRITE-from-code's anchor is the verbatim
    pin done in code, not this reply — so a wrong value here just fails to pin -> NO_EVIDENCE."""
    def locate(aspect: str, code: str) -> str | None:
        system = (
            "Find where the named training/model aspect is set in the code and report ONLY its "
            "literal value EXACTLY as written in the source (e.g. 8, 1e-4, Adam, z-score), or "
            "NONE if the code does not set it. Copy the token verbatim — do not normalize."
        )
        user = f"Aspect: {aspect}\n\nCode:\n```\n{code}\n```\n\nLiteral value:"
        return _clean_value(_complete(system, user, model=model, max_tokens=16))

    return locate


def make_code_writer(model: str = DEEPSEEK) -> CodeWriter:
    """Write one Methods sentence for an aspect, grounded in the value + the code line it came
    from. The verbatim pin is enforced by codewrite; the writer only phrases it."""
    def writer(aspect: str, value: str, code_line: str) -> str:
        system = (
            "You are writing the Methods section of an ML paper. Write a SINGLE precise, formal "
            "sentence reporting how the given aspect is configured, using the exact value. State "
            "only what the value and code line support — add no numbers or claims beyond them. "
            "Output ONLY the sentence."
        )
        user = f"Aspect: {aspect}\nValue: {value}\nCode line: {code_line}\n\nSentence:"
        return _complete(system, user, model=model, max_tokens=80)

    return writer


def make_generator(model: str = DEEPSEEK) -> Generator:
    def generator(card: SpecCard) -> str:
        fields = "\n".join(f"- {_field_brief(f)}" for f in card.fields)
        system = (
            "Generate a minimal Python training snippet that honors ALL the given "
            "reproducibility constraints exactly. Output ONLY code, no prose, no fences."
        )
        user = f"Constraints for method {card.method}:\n{fields}\n\nCode:"
        return _complete(system, user, model=model, max_tokens=512)

    return generator
