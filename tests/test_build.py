"""Contract for the card-builder bridge (review F1): str-valued extraction -> typed ValueSpec.

Centralizes the str->type coercion that was duplicated (and fragile: int() on '0.0001'
truncates) across examples. Fails LOUD on un-parseable numerics and refuses a silent exact
float compare.
"""
import pytest

from specrag import Cat, LocatorKind, Phase, ValueKind, VLevel
from specrag.build import build_field, build_value_spec
from specrag.speccard import Jumper


def _jumper() -> Jumper:
    return Jumper(pq_dockey="d", verbatim_text="batch size of 8", anchor_phrase="batch size of 8")


def test_build_int():
    vs = build_value_spec("8", ValueKind.NUMERIC)
    assert vs.equals == 8
    assert isinstance(vs.equals, int)


def test_build_float_requires_tolerance():
    with pytest.raises(ValueError):
        build_value_spec("1e-4", ValueKind.NUMERIC)  # no atol/rtol -> refuse silent exact float
    vs = build_value_spec("1e-4", ValueKind.NUMERIC, atol=1e-6)
    assert vs.equals == pytest.approx(1e-4)
    assert vs.atol == 1e-6


def test_build_dotted_float_requires_tolerance():
    with pytest.raises(ValueError):
        build_value_spec("8.0", ValueKind.NUMERIC)


def test_build_numeric_unparseable_raises_loud():
    with pytest.raises(ValueError):
        build_value_spec("eight", ValueKind.NUMERIC)


def test_build_sci_notation_integer_is_int():
    vs = build_value_spec("1e5", ValueKind.NUMERIC)
    assert vs.equals == 100000
    assert isinstance(vs.equals, int)
    assert build_value_spec("2E4", ValueKind.NUMERIC).equals == 20000


def test_build_signed_int():
    assert build_value_spec("-1", ValueKind.NUMERIC).equals == -1
    assert build_value_spec("+8", ValueKind.NUMERIC).equals == 8


def test_build_rejects_underscore_and_comma():
    with pytest.raises(ValueError):
        build_value_spec("1_000", ValueKind.NUMERIC)
    with pytest.raises(ValueError):
        build_value_spec("1,000", ValueKind.NUMERIC)


def test_build_numeric_none_raises():
    with pytest.raises(ValueError):
        build_value_spec(None, ValueKind.NUMERIC)


def test_build_enum():
    vs = build_value_spec("z-score", ValueKind.ENUM, aliases=["zero mean unit variance"])
    assert vs.equals == "z-score"
    assert vs.aliases == ["zero mean unit variance"]


def test_build_range():
    vs = build_value_spec(None, ValueKind.RANGE, low=1e-5, high=1e-3)
    assert vs.low == 1e-5
    assert vs.high == 1e-3


def test_build_field_assembles_spec_field():
    f = build_field(
        "batch_size", "8", value_kind=ValueKind.NUMERIC, locator_kind=LocatorKind.LITERAL,
        category=Cat.HYPERPARAMETER, jumper=_jumper(), verification_level=VLevel.SELF,
        moat_critical=True,
    )
    assert f.name == "batch_size"
    assert f.value_spec.equals == 8
    assert f.verification_level == VLevel.SELF
    assert f.moat_critical is True


def test_build_field_augmentation_needs_phase():
    # build_field must still satisfy SpecField validators (augmentation -> phase)
    f = build_field(
        "jitter", "intensity_jitter", value_kind=ValueKind.ENUM, locator_kind=LocatorKind.SEMANTIC,
        category=Cat.AUGMENTATION, jumper=_jumper(), phase=Phase.EVAL,
    )
    assert f.phase == Phase.EVAL
