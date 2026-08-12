#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcpmodel.external_annotation import create_external_annotation_pack
from mcpmodel.validator import iter_documents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--derived", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = []
    for path in sorted(args.derived.glob("*.jsonl")):
        if path.name == "sources.jsonl":
            continue
        records.extend(document for _, document in iter_documents(path))
    print(
        json.dumps(
            create_external_annotation_pack(records, args.output),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
