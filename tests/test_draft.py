"""Contract tests for WRITE-from-papers (draft.py). Fakes for retrieve/write/judge/extractor,
mirroring the rest of the suite. We test the contract — the anti-hallucination invariant —
not "the prose is good"."""
from __future__ import annotations

from rag_research.claim import ClaimVerdict
from rag_research.draft import (
    DraftStatus,
    draft_bullet,
    draft_section,
    render_draft_section,
)
from rag_research.substrate import Passage


def _passage(text: str, cite: str = "Doe 2024") -> Passage:
    return Passage(pq_dockey="dk", verbatim_text=text, page_range="pages 1-2", doc_citation=cite)


def _retrieve_with(text: str):
    return lambda q, k: [_passage(text)]


_retrieve_empty = lambda q, k: []  # noqa: E731


def _write_echo(bullet, passages):
    # writer that grounds itself in the top passage (honest writer)
    return passages[0]


def _judge_const(verdict: ClaimVerdict):
    return lambda text, passages: verdict


_no_extract = lambda text, passages: None  # noqa: E731


# ---- polarity 1: evidence present + judge HONORED -> ANCHORED, sentence written ----
def test_anchored_when_supported():
    card = draft_bullet(
        "TCAV explains models",
        retrieve=_retrieve_with("TCAV provides concept-level explanations of models."),
        write=_write_echo,
        judge=_judge_const(ClaimVerdict.HONORED),
        extractor=_no_extract,
    )
    assert card.status == DraftStatus.ANCHORED
    assert card.claim_text
    assert card.jumper is not None
    assert card.source == "Doe 2024"


# ---- polarity 2: no passages -> NO_EVIDENCE, never invents ----
def test_no_evidence_when_corpus_silent():
    card = draft_bullet(
        "Quantum disease detection is solved",
        retrieve=_retrieve_empty,
        write=_write_echo,
        judge=_judge_const(ClaimVerdict.HONORED),
        extractor=_no_extract,
    )
    assert card.status == DraftStatus.NO_EVIDENCE
    assert card.claim_text == ""
    assert card.jumper is None


# ---- polarity 3: writer hallucinates -> judge UNSUPPORTED -> NO_EVIDENCE (not written) ----
def test_hallucinating_writer_downgraded():
    def _write_hallucinate(bullet, passages):
        return "The model achieves 99.9% accuracy on a dataset never mentioned."

    card = draft_bullet(
        "model accuracy",
        retrieve=_retrieve_with("The paper reports a Dice score on thyroid ultrasound."),
        write=_write_hallucinate,
        judge=_judge_const(ClaimVerdict.UNSUPPORTED),
        extractor=_no_extract,
    )
    assert card.status == DraftStatus.NO_EVIDENCE
    assert card.jumper is None


def test_writer_no_support_sentinel_is_no_evidence():
    # The writer says it can't ground the bullet -> NO_EVIDENCE, never judged into the prose.
    # (Regression: a live writer turned this into a vacuously-true "not mentioned" sentence that
    # the judge HONORED, leaking an unsupported bullet into the draft.)
    def _write_no_support(bullet, passages):
        return "NO_SUPPORT"

    card = draft_bullet(
        "a topic the corpus does not cover",
        retrieve=_retrieve_with("Some unrelated evidence."),
        write=_write_no_support,
        judge=_judge_const(ClaimVerdict.HONORED),  # judge would HONOR, but we never reach it
        extractor=_no_extract,
    )
    assert card.status == DraftStatus.NO_EVIDENCE
    assert card.claim_text == ""


def test_ambiguous_goes_to_human_queue():
    card = draft_bullet(
        "borderline claim",
        retrieve=_retrieve_with("Some hedged statement about results."),
        write=_write_echo,
        judge=_judge_const(ClaimVerdict.AMBIGUOUS),
        extractor=_no_extract,
    )
    assert card.status == DraftStatus.AMBIGUOUS


def _retriever_silent_for(*silent: str):
    """Realistic fake: returns evidence for any query EXCEPT the listed silent ones.
    verify_claim re-retrieves with the written sentence, so keying on exact bullet text
    would break — a silent SET keeps both the bullet and the echoed sentence consistent."""
    silent_set = set(silent)
    return lambda q, k: [] if q in silent_set else [_passage("Evidence about something.")]


def test_section_counts_and_helpers():
    outline = ["good bullet", "bad bullet"]
    retr = _retriever_silent_for("bad bullet")
    section = draft_section(
        outline,
        retrieve=retr,
        write=_write_echo,
        judge=_judge_const(ClaimVerdict.HONORED),
        extractor=_no_extract,
    )
    assert len(section.cards) == 2
    assert section.no_evidence_count() == 1
    assert len(section.anchored()) == 1
    assert section.cards[0].claim_text  # ids 1-based, order preserved


def test_render_keeps_no_evidence_visible():
    outline = ["supported point", "unsupported point"]
    retr = _retriever_silent_for("unsupported point")
    section = draft_section(
        outline,
        retrieve=retr,
        write=_write_echo,
        judge=_judge_const(ClaimVerdict.HONORED),
        extractor=_no_extract,
    )
    md = render_draft_section(section, title="Related Work")
    assert "# Related Work" in md
    assert "SIN EVIDENCIA: unsupported point" in md       # visible, not dropped
    assert "Trazabilidad" in md
    assert "Sin evidencia: 1 de 2 bullets." in md
    assert "[Doe 2024]" in md                              # inline citation on anchored prose
