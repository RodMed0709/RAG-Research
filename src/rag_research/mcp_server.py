"""rag_research MCP server (the ``[mcp]`` extra).

Lets another Claude Code session / agent use rag_research as a grounded verification tool:
Claude orchestrates, rag_research (with DeepSeek inside) does the grounded, traceable check. The
calling model never has to hold reproducibility norms in its volatile memory — it asks this
tool, which compares against typed spec-cards.

Run directly:  python -m rag_research.mcp_server
Or register in an MCP client (e.g. Claude Code) pointing at that command. Needs the ``[mcp]``
extra (fastmcp) and ``DEEPSEEK_API_KEY`` in the environment / a local ``.env``.
"""
from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from .codegen import Stamp, check_stamp
from .speccard import SpecCard
from .verify import FieldVerdict, verify_consistency

mcp: FastMCP = FastMCP("RAG-Research")


def _verdict_dict(v: FieldVerdict) -> dict[str, object]:
    return {
        "field": v.field_name,
        "state": v.state.value,
        "blocked": v.blocked,
        "needs_human": v.needs_human,
        "source": v.verdict_source,
        "code_evidence": v.code_evidence,
    }


def _load_keys() -> None:
    """Find DEEPSEEK_API_KEY's .env whether the server is launched from the project dir or
    elsewhere (an MCP client may spawn it with any cwd)."""
    from .llm import load_env

    here = Path(__file__).resolve()
    for candidate in (Path.cwd() / ".env", here.parents[2] / ".env"):
        load_env(candidate)


def _verify(card_json: str, code: str) -> dict[str, object]:
    from .llm import make_judge, make_locator

    _load_keys()
    card = SpecCard.model_validate_json(card_json)
    verdicts = verify_consistency(card, code, locate=make_locator(), judge=make_judge())
    blocked = any(v.blocked for v in verdicts)
    human = any(v.needs_human for v in verdicts)
    outcome = "blocked" if blocked else ("held_for_human" if human else "ok")
    return {
        "card_id": card.card_id,
        "version": card.version,
        "outcome": outcome,
        "verdicts": [_verdict_dict(v) for v in verdicts],
    }


@mcp.tool
def verify_code_against_card(card_json: str, code: str) -> dict[str, object]:
    """Verify a code snippet against a spec-card (JSON string).

    Hard fields (batch_size, lr, ...) are compared DETERMINISTICALLY; only semantic fields
    (e.g. augmentation phase) go to the LLM. Returns per-field verdicts and an overall
    ``outcome``: ``ok`` / ``held_for_human`` / ``blocked``. Use before trusting generated ML
    code: it tells you, traceably, which of the paper's reproducibility norms the code honors.
    """
    return _verify(card_json, code)


@mcp.tool
def verify_file_against_card(card_path: str, code_path: str) -> dict[str, object]:
    """Like ``verify_code_against_card`` but reads the spec-card JSON and the code from file paths."""
    card_json = Path(card_path).read_text(encoding="utf-8")
    code = Path(code_path).read_text(encoding="utf-8")
    return _verify(card_json, code)


@mcp.tool
def check_code_stamp(stamp_json: str, current_card_json: str) -> dict[str, object]:
    """Check whether code stamped against an earlier card version is now STALE.

    Pass the stamp (JSON) the code was generated with and the current spec-card (JSON). Returns
    whether the code drifted (a value/phase/field changed on re-extraction) and which fields.
    """
    stamp = Stamp.model_validate_json(stamp_json)
    card = SpecCard.model_validate_json(current_card_json)
    report = check_stamp(stamp, card)
    return {"stale": report.stale, "reason": report.reason, "changed_fields": report.changed_fields}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
