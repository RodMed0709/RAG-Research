"""Contract tests for the spec-card schema (Phase 1, Tasks 1.1-1.4).

These encode the hard rules from speccard_schema.md §7. Implementation in
src/specrag/speccard.py must satisfy them.
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from specrag import (
    Cat,
    Jumper,
    LocatorKind,
    Phase,
    SpecCard,
    SpecField,
    ValueKind,
    ValueSpec,
    VLevel,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "cards"


def _jumper(**kw) -> Jumper:
    base = dict(pq_dockey="d1", verbatim_text="batch size of 8 per GPU", anchor_phrase="batch size of 8")
    base.update(kw)
    return Jumper(**base)


def _hard_field(**kw) -> SpecField:
    base = dict(
        name="batch_size",
        category=Cat.HYPERPARAMETER,
        value_kind=ValueKind.NUMERIC,
        locator_kind=LocatorKind.LITERAL,
        value_spec=ValueSpec(kind=ValueKind.NUMERIC, equals=8),
        jumper=_jumper(),
    )
    base.update(kw)
    return SpecField(**base)


# --- Task 1.1: Jumper ---

def test_jumper_requires_verbatim():
    Jumper(pq_dockey="d", verbatim_text="x", anchor_phrase="x")  # ok
    with pytest.raises(ValidationError):
        Jumper(pq_dockey="d", anchor_phrase="x")  # missing verbatim_text


# --- Task 1.2: SpecField validators (schema §7) ---

def test_augmentation_requires_phase():
    # augmentation WITH phase is fine
    _hard_field(name="jitter", category=Cat.AUGMENTATION, phase=Phase.EVAL)
    # augmentation WITHOUT phase is invalid
    with pytest.raises(ValidationError):
        _hard_field(name="jitter", category=Cat.AUGMENTATION, phase=None)


def test_not_reported_requires_searched_passages():
    # not_reported needs evidence of where we looked
    SpecField(
        name="dropout",
        category=Cat.HYPERPARAMETER,
        value_kind=ValueKind.NUMERIC,
        locator_kind=LocatorKind.LITERAL,
        value_spec=ValueSpec(kind=ValueKind.NUMERIC),
        not_reported=True,
        searched_passages=[_jumper(verbatim_text="weight decay 1e-4", anchor_phrase="weight decay")],
        jumper=None,
    )
    with pytest.raises(ValidationError):
        SpecField(
            name="dropout",
            category=Cat.HYPERPARAMETER,
            value_kind=ValueKind.NUMERIC,
            locator_kind=LocatorKind.LITERAL,
            value_spec=ValueSpec(kind=ValueKind.NUMERIC),
            not_reported=True,
            searched_passages=None,
            jumper=None,
        )


def test_reported_requires_jumper():
    with pytest.raises(ValidationError):
        SpecField(
            name="batch_size",
            category=Cat.HYPERPARAMETER,
            value_kind=ValueKind.NUMERIC,
            locator_kind=LocatorKind.LITERAL,
            value_spec=ValueSpec(kind=ValueKind.NUMERIC, equals=8),
            not_reported=False,
            jumper=None,
        )


def test_value_in_media_requires_media():
    with pytest.raises(ValidationError):
        _hard_field(name="eq1", category=Cat.EQUATION, value_in_media=True, jumper=_jumper(media=None))
    # with media bytes it is valid
    _hard_field(name="eq1", category=Cat.EQUATION, value_in_media=True, jumper=_jumper(media=b"\x89PNG"))


# --- Task 1.3: SpecCard + non-blocking summary ---

def test_card_summary_counts():
    f_human = _hard_field(verification_level=VLevel.HUMAN, moat_critical=True)
    f_self = _hard_field(name="lr", verification_level=VLevel.SELF, moat_critical=True)
    f_unv = _hard_field(name="seed", verification_level=VLevel.UNVERIFIED, moat_critical=False)
    card = SpecCard(
        card_id="p::m", paper_ref="p", method="m",
        fields=[f_human, f_self, f_unv],
    )
    summary = card.verification_summary()
    assert summary["human"] == 1
    assert summary["self"] == 1
    assert summary["unverified"] == 1
    # min among moat-critical fields only (human, self) -> "self-consistent", not unverified
    assert summary["min_moat_critical"] == VLevel.SELF.value


# --- Task 1.4: example cards load ---

@pytest.mark.parametrize("name", [
    "zhou2023thyroid__MedSAM-ft.json",
    "lee2022echo__nnU-Net.json",
])
def test_example_cards_load(name):
    data = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    card = SpecCard.model_validate(data)
    assert card.fields
    assert card.card_id == f"{card.paper_ref}::{card.method}"
