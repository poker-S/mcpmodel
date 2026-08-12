#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcpmodel.pilot import write_pilot
from mcpmodel.splitting import group_split, split_manifest
from mcpmodel.validator import iter_documents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/pilot/pilot-0.1.jsonl"))
    parser.add_argument("--split-output", type=Path, default=Path("data/splits/pilot-0.1.json"))
    parser.add_argument("--seed", type=int, default=20260812)
    args = parser.parse_args()

    pilot_manifest = write_pilot(args.output)
    cases = [document for _, document in iter_documents(args.output)]
    splits = group_split(cases, seed=args.seed)
    args.split_output.parent.mkdir(parents=True, exist_ok=True)
    split_summary = split_manifest(splits, args.seed)
    args.split_output.write_text(
        json.dumps(split_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"pilot": pilot_manifest, "split": split_summary}, ensure_ascii=False, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
