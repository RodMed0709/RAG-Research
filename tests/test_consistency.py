from rag_research.consistency import (
    Severity,
    confusion_matrix_check,
    detect_missing_sections,
    detect_terminology_variants,
    render_review,
)


def test_terminology_variants_flagged():
    text = "We use Grad-CAM here and GradCAM there, plus Grad-CAM again."
    out = detect_terminology_variants(text, [["Grad-CAM", "GradCAM", "grad-cam"]])
    assert len(out) == 1
    assert out[0].severity == Severity.FORM
    assert "Grad-CAM" in out[0].suggestion


def test_terminology_consistent_no_flag():
    text = "We consistently use Grad-CAM and only Grad-CAM."
    assert detect_terminology_variants(text, [["Grad-CAM", "GradCAM"]]) == []


def test_confusion_matrix_mismatch_percentage():
    # recall = 11/(11+4) = 0.7333; text claims 84.85% -> mismatch
    out = confusion_matrix_check(11, 2, 4, 100, {"recall": 84.85})
    assert len(out) == 1
    assert out[0].severity == Severity.MAJOR
    assert out[0].category == "metrics"


def test_confusion_matrix_match_fraction():
    # recall = 11/15 = 0.7333; claim 0.73 within atol -> ok
    assert confusion_matrix_check(11, 2, 4, 100, {"recall": 0.7333}) == []


def test_confusion_matrix_guards_zero_denominator():
    # no positives at all -> recall/precision skipped, accuracy still computable
    out = confusion_matrix_check(0, 0, 0, 10, {"recall": 0.5, "accuracy": 1.0})
    assert out == []  # recall skipped (no denom), accuracy 1.0 matches


def test_missing_sections():
    out = detect_missing_sections(["Introducción", "Métodos", "Resultados"], ["Conclusión"])
    assert len(out) == 1
    assert out[0].severity == Severity.MAJOR


def test_render_review_groups_by_severity():
    findings = (
        detect_missing_sections([], ["Conclusión"])
        + detect_terminology_variants("Grad-CAM GradCAM", [["Grad-CAM", "GradCAM"]])
    )
    md = render_review(findings)
    assert "🔴 Mayores" in md
    assert "✍️ Forma" in md
    # major appears before form
    assert md.index("🔴") < md.index("✍️")


def test_render_review_empty():
    assert render_review([]) == "# Revisión\n\n_Sin hallazgos._"
