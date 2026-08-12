#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcpmodel.annotation import create_annotation_pack
from mcpmodel.validator import iter_documents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/pilot/pilot-0.1.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = [document for _, document in iter_documents(args.data)]
    print(json.dumps(create_annotation_pack(cases, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
