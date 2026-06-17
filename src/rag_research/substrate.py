"""Thin wrapper over PaperQA2 (the ``[paperqa]`` extra).

Responsibilities: ingest PDFs, retrieve raw verbatim passages (no LLM synthesis), and
bridge a passage + a located value into a self-sufficient ``Jumper``. The verify core
never imports this module — only the extraction/substrate path does.

Identity rule (schema §1): the stable ``paper_ref`` is rag_research's own (DOI or canonical
slug), NEVER PaperQA2's ``dockey`` (an unstable md5 of file bytes). The dockey is kept
on the jumper only as a mutable re-fetch handle.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .speccard import Jumper

if TYPE_CHECKING:  # avoid importing the heavy extra at module load
    pass

_PAGES_RE = re.compile(r"pages?\s+(\d+)(?:\s*[-–]\s*(\d+))?", re.IGNORECASE)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def parse_page_range(text_name: str | None) -> str | None:
    """Parse ``"... pages X-Y"`` from a PaperQA2 ``Text.name``. Defensive: None if absent
    (plain-text/code chunks carry no page; schema MENOR-2)."""
    if not text_name:
        return None
    m = _PAGES_RE.search(text_name)
    if not m:
        return None
    lo, hi = m.group(1), m.group(2)
    return f"pages {lo}-{hi}" if hi else f"pages {lo}"


def slugify_ref(name: str) -> str:
    """Canonical, stable paper_ref slug when no DOI is available."""
    s = _SLUG_RE.sub("-", name.lower()).strip("-")
    return s or "paper"


@dataclass(frozen=True)
class Passage:
    """A raw retrieved passage. Verbatim is cached here; the jumper is assembled when a
    value is pinned inside it (during extraction)."""

    pq_dockey: str
    verbatim_text: str
    page_range: str | None
    doc_citation: str
    score: float | None = None


def make_jumper(passage: Passage, value: str, *, window: int = 40) -> Jumper | None:
    """Bridge a passage + a located literal into a self-sufficient Jumper.

    Locates ``value`` inside the cached verbatim, derives an ``anchor_phrase`` window and a
    ``char_span`` *relative to anchor_phrase* (schema §5: span within the phrase, not the
    raw token, to avoid homonyms). Returns None if the value is not present, or AMBIGUOUS
    (caller's job) if it appears more than once.
    """
    text = passage.verbatim_text
    first = text.find(value)
    if first < 0:
        return None
    # more than one occurrence -> the span is ambiguous; signal by leaving char_span None
    ambiguous = text.find(value, first + 1) != -1
    start = max(0, first - window)
    end = min(len(text), first + len(value) + window)
    anchor = text[start:end].strip()
    char_span: tuple[int, int] | None = None
    if not ambiguous:
        rel = anchor.find(value)
        if rel >= 0:
            char_span = (rel, rel + len(value))
    return Jumper(
        pq_dockey=passage.pq_dockey,
        verbatim_text=text,
        anchor_phrase=anchor,
        page_range=passage.page_range,
        char_span=char_span,
    )


class Substrate:
    """Live wrapper over a PaperQA2 ``Docs`` store. Constructed lazily so the verify core
    stays importable without the ``[paperqa]`` extra installed."""

    def __init__(self, embedding_model: Any = None, settings: Any = None) -> None:
        try:
            from paperqa import Docs, Settings
        except ImportError as e:  # pragma: no cover - exercised only without the extra
            raise ImportError("Substrate needs the [paperqa] extra: pip install 'rag-research[paperqa]'") from e
        self._Settings = Settings
        self.docs = Docs()
        self.settings = settings if settings is not None else self._local_settings()
        self.embedding_model = embedding_model

    #: Local SentenceTransformer embedding (the ``st-`` prefix routes lmi to a local model).
    #: Keeps retrieval fully offline — no OpenAI/embedding API key needed.
    DEFAULT_EMBEDDING = "st-multi-qa-MiniLM-L6-cos-v1"

    def _local_settings(self) -> Any:
        s = self._Settings()
        # offline-friendly: no LLM-driven metadata inference, and no multimodal image
        # enrichment (which captions figures via an LLM). Media/equation extraction is a
        # later, human-confirmed path; text retrieval needs neither.
        s.parsing.use_doc_details = False
        s.parsing.multimodal = False
        # Use a LOCAL embedding model. Without this, PaperQA2 defaults to an OpenAI embedding
        # and ingest fails for users who only have a non-OpenAI LLM key (e.g. DeepSeek).
        s.embedding = self.DEFAULT_EMBEDDING
        return s

    async def ingest(self, path: str, *, paper_ref: str | None = None, citation: str | None = None) -> str:
        ref = paper_ref or slugify_ref(str(path).rsplit("/", 1)[-1].rsplit(".", 1)[0])
        await self.docs.aadd(
            path, citation=citation or ref, docname=ref,
            settings=self.settings, embedding_model=self.embedding_model,
        )
        return ref

    async def retrieve(self, query: str, k: int = 8) -> list[Passage]:
        texts = await self.docs.retrieve_texts(
            query, k, settings=self.settings, embedding_model=self.embedding_model,
        )
        return [
            Passage(
                pq_dockey=str(t.doc.dockey),
                verbatim_text=t.text,
                page_range=parse_page_range(t.name),
                doc_citation=getattr(t.doc, "citation", ""),
            )
            for t in texts
        ]
