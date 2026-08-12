#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcpmodel.authorization_reconstruction import create_authorization_reconstruction_pack
from mcpmodel.normalizer import ToolNormalizer
from mcpmodel.validator import iter_documents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--derived", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--normalization-config",
        type=Path,
        default=Path("configs/tool_normalization.yaml"),
    )
    args = parser.parse_args()
    records = []
    for path in sorted(args.derived.glob("*.jsonl")):
        if path.name == "sources.jsonl":
            continue
        records.extend(document for _, document in iter_documents(path))
    manifest = create_authorization_reconstruction_pack(
        records, args.output, ToolNormalizer(args.normalization_config)
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
