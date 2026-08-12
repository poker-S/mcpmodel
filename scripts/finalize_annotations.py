#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcpmodel.annotation import finalize_human_labels


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sheets", nargs="+", type=Path)
    parser.add_argument("--adjudication", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = finalize_human_labels(args.sheets, args.adjudication, args.output)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
