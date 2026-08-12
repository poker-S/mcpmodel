"""Command-line entry point for validating project data artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mcpmodel.validator import ValidationFailure, discover_inputs, iter_documents, validate_document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate MCPModel JSON/JSONL artifacts")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument(
        "--schema", choices=("case", "authorization", "audit_event"), default="case"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checked = 0
    try:
        for path in discover_inputs(args.paths):
            for location, document in iter_documents(path):
                validate_document(document, args.schema)
                print(f"OK {location}")
                checked += 1
    except (FileNotFoundError, OSError, ValueError, ValidationFailure) as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1
    print(f"validated={checked} schema={args.schema}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
