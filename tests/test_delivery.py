from rag_research.delivery import (
    TrackedChange,
    latex_tracked,
    render_latex_changes,
    render_tracked_changes,
)


def _c() -> TrackedChange:
    return TrackedChange(
        before="usamos TCAV", after="usamos análisis de conceptos latentes (inspirado en TCAV)",
        reason="la implementación no es TCAV real (Kim 2018)", location="Sec. G",
    )


def test_tracked_changes_markdown():
    md = render_tracked_changes([_c()])
    assert "# Cambios marcados" in md
    assert "❌ usamos TCAV" in md
    assert "✅ usamos análisis" in md
    assert "💡 la implementación" in md
    assert "_Sec. G_" in md


def test_tracked_changes_empty():
    assert render_tracked_changes([]) == "# Cambios marcados\n\n_Sin cambios._"


def test_latex_tracked_markup():
    out = latex_tracked(_c())
    assert r"\textcolor{red}{\st{usamos TCAV}}" in out
    assert r"\textcolor{blue}{" in out


def test_latex_tracked_insertion_only():
    out = latex_tracked(TrackedChange(before="", after="nuevo texto", reason="añadir"))
    assert out == r"\textcolor{blue}{nuevo texto}"


def test_render_latex_changes_list():
    snippet = render_latex_changes([_c()])
    assert r"\begin{itemize}" in snippet
    assert r"\end{itemize}" in snippet
    assert "% la implementación" in snippet  # reason as comment
