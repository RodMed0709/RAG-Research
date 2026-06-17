"""Internal-consistency checks on a manuscript — no external evidence needed.

Catches what a reviewer flags from the text alone: inconsistent terminology, metrics that
don't match the confusion matrix, missing required sections. Deterministic and pure.
"""
from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel


class Severity(str, Enum):
    MAJOR = "major"  # 🔴 blocks publication
    MINOR = "minor"  # 🟡 quality
    FORM = "form"    # ✍️ style / wording


class Finding(BaseModel):
    severity: Severity
    category: str
    message: str
    location: str | None = None
    suggestion: str | None = None


def detect_terminology_variants(text: str, groups: list[list[str]]) -> list[Finding]:
    """For each group of equivalent spellings, flag when more than one variant is used.
    Case-sensitive (so "Grad-CAM" and "GradCAM" are distinct), whole-token match."""
    findings: list[Finding] = []
    for group in groups:
        present: list[str] = []
        for variant in group:
            # \b is unreliable around hyphens; require a non-word char (or string edge) on
            # each side so "GradCAM" inside "Grad-CAM" doesn't false-match.
            pat = rf"(?<![\w-]){re.escape(variant)}(?![\w-])"
            if re.search(pat, text):
                present.append(variant)
        if len(present) > 1:
            canonical = group[0]
            findings.append(
                Finding(
                    severity=Severity.FORM,
                    category="terminology",
                    message=f"Uso inconsistente: {present}. Unificar a '{canonical}'.",
                    suggestion=canonical,
                )
            )
    return findings


def confusion_matrix_check(
    tp: int, fp: int, fn: int, tn: int, claimed: dict[str, float], *, atol: float = 0.01
) -> list[Finding]:
    """Recompute recall/precision/accuracy from the confusion matrix and compare to the
    values the text reports. Claimed values may be percentages (84.85) or fractions (0.8485)."""
    computed: dict[str, float] = {}
    if tp + fn:
        computed["recall"] = tp / (tp + fn)
    if tp + fp:
        computed["precision"] = tp / (tp + fp)
    total = tp + fp + fn + tn
    if total:
        computed["accuracy"] = (tp + tn) / total

    findings: list[Finding] = []
    for metric, claimed_val in claimed.items():
        if metric not in computed:
            continue
        norm = claimed_val / 100.0 if claimed_val > 1.0 else claimed_val
        if abs(computed[metric] - norm) > atol:
            findings.append(
                Finding(
                    severity=Severity.MAJOR,
                    category="metrics",
                    message=(
                        f"{metric}: la matriz de confusión da {computed[metric]:.4f} "
                        f"pero el texto reporta {claimed_val}."
                    ),
                    suggestion="Reconciliar matriz de confusión con la métrica reportada y con n_test.",
                )
            )
    return findings


def detect_missing_sections(present: list[str], required: list[str]) -> list[Finding]:
    """Flag required sections absent from the manuscript. Case-insensitive substring match."""
    low = [p.lower() for p in present]
    findings: list[Finding] = []
    for req in required:
        if not any(req.lower() in p for p in low):
            findings.append(
                Finding(
                    severity=Severity.MAJOR,
                    category="structure",
                    message=f"Falta la sección obligatoria: '{req}'.",
                    suggestion=f"Añadir sección '{req}'.",
                )
            )
    return findings


_SEV_HEADING = {
    Severity.MAJOR: "## 🔴 Mayores",
    Severity.MINOR: "## 🟡 Menores",
    Severity.FORM: "## ✍️ Forma",
}


def render_review(findings: list[Finding], *, title: str = "Revisión") -> str:
    """Render findings as REVIEW.md, grouped by severity (major → minor → form)."""
    if not findings:
        return f"# {title}\n\n_Sin hallazgos._"
    lines = [f"# {title}", ""]
    for sev in (Severity.MAJOR, Severity.MINOR, Severity.FORM):
        group = [f for f in findings if f.severity == sev]
        if not group:
            continue
        lines.append(_SEV_HEADING[sev])
        for f in group:
            line = f"- **[{f.category}]** {f.message}"
            if f.location:
                line += f" _(en {f.location})_"
            if f.suggestion:
                line += f" → {f.suggestion}"
            lines.append(line)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
