"""RAG-Research command-line interface.

    rag-research verify <card.json> <code.py>

Loads a spec-card, reads a code file, and runs ``verify_consistency`` using DeepSeek (via
``.env``) as the semantic judge and the code-value locator. Exit code: 0 = OK, 1 = held for
human, 2 = blocked. The card identity/version stays rag_research's; the LLM only locates & judges.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from .speccard import SpecCard
from .verify import verify_consistency


def _verify_cmd(card_path: str, code_path: str) -> int:
    try:
        card = SpecCard.model_validate_json(Path(card_path).read_text(encoding="utf-8"))
        code = Path(code_path).read_text(encoding="utf-8")
    except (OSError, ValidationError) as e:
        print(f"error: could not load inputs: {e}", file=sys.stderr)
        return 3

    from .llm import load_env, make_judge, make_locator

    load_env()

    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("error: DEEPSEEK_API_KEY not set (put it in .env or the environment).", file=sys.stderr)
        return 3

    verdicts = verify_consistency(card, code, locate=make_locator(), judge=make_judge())

    print(f"card {card.card_id} v{card.version}  vs  {Path(code_path).name}\n")
    blocked = human = False
    for v in verdicts:
        blocked = blocked or v.blocked
        human = human or v.needs_human
        mark = "BLOCK" if v.blocked else ("HUMAN" if v.needs_human else "ok")
        print(f"  [{mark:>5}] {v.field_name:<22} {v.state.value:<14} via {v.verdict_source}")

    outcome = "BLOCKED" if blocked else ("HELD for human" if human else "OK")
    print(f"\n{outcome}")
    return 2 if blocked else (1 if human else 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rag-research", description=((__doc__ or "").splitlines() or [""])[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    pv = sub.add_parser("verify", help="verify a code file against a spec-card")
    pv.add_argument("card", help="path to a spec-card JSON file")
    pv.add_argument("code", help="path to the code file to check")

    args = parser.parse_args(argv)
    if args.cmd == "verify":
        return _verify_cmd(args.card, args.code)
    return 1


if __name__ == "__main__":
    sys.exit(main())
