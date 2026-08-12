#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcpmodel.annotation import agreement_report, write_adjudication_queue


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sheets", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--adjudication", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = agreement_report(args.sheets)
    except ValueError as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_adjudication_queue(args.adjudication, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
