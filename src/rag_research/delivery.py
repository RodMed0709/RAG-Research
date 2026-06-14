"""Deliverables for the reviewer hand-off: tracked changes in Markdown and LaTeX.

A ``TrackedChange`` is one before→after edit with a reason. We render it two ways: a
human-readable ``CAMBIOS_MARCADOS.md`` (❌/✅/💡) and LaTeX tracked-changes markup that drops
into an Overleaf project. The actual *rewriting* of paragraphs (anchored to verified
evidence) is the agentic layer's job; this module only formats the result.
"""
from __future__ import annotations

import shutil
import subprocess

from pydantic import BaseModel


class TrackedChange(BaseModel):
    before: str
    after: str
    reason: str
    location: str | None = None


# Drop this in the LaTeX preamble for the inline markup below to compile.
LATEX_PREAMBLE = r"\usepackage{soul}" + "\n" + r"\usepackage{xcolor}"


def render_tracked_changes(changes: list[TrackedChange], *, title: str = "Cambios marcados") -> str:
    """CAMBIOS_MARCADOS.md — one block per change: ❌ current / ✅ new / 💡 reason."""
    if not changes:
        return f"# {title}\n\n_Sin cambios._"
    lines = [f"# {title}", ""]
    for i, c in enumerate(changes, 1):
        where = f" — _{c.location}_" if c.location else ""
        lines += [
            f"## {i}.{where}",
            f"- ❌ {c.before}",
            f"- ✅ {c.after}",
            f"- 💡 {c.reason}",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def latex_tracked(change: TrackedChange) -> str:
    """Inline LaTeX tracked-change markup: struck-out red old text + blue new text.
    Requires ``soul`` and ``xcolor`` (see LATEX_PREAMBLE)."""
    old = f"\\textcolor{{red}}{{\\st{{{change.before}}}}}" if change.before else ""
    new = f"\\textcolor{{blue}}{{{change.after}}}" if change.after else ""
    sep = " " if old and new else ""
    return f"{old}{sep}{new}"


def render_latex_changes(changes: list[TrackedChange]) -> str:
    """A LaTeX snippet: preamble note + an itemized list of tracked changes, ready to paste."""
    lines = [f"% Preamble:\n% {LATEX_PREAMBLE.replace(chr(10), chr(10) + '% ')}", "", r"\begin{itemize}"]
    for c in changes:
        loc = f" ({c.location})" if c.location else ""
        lines.append(f"  \\item{loc} {latex_tracked(c)} \\quad % {c.reason}")
    lines.append(r"\end{itemize}")
    return "\n".join(lines)


def latexdiff_files(old_tex: str, new_tex: str) -> str:
    """Run ``latexdiff`` over two .tex files and return the diff document. Raises if the
    ``latexdiff`` binary is not on PATH (it ships with most TeX distributions)."""
    if shutil.which("latexdiff") is None:
        raise FileNotFoundError("latexdiff not on PATH (install a TeX distribution, e.g. TeX Live)")
    result = subprocess.run(  # noqa: S603 - fixed binary, caller-supplied paths
        ["latexdiff", old_tex, new_tex],
        capture_output=True, text=True, check=True,
    )
    return result.stdout
