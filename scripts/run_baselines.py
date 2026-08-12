#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcpmodel.baseline import write_run
from mcpmodel.validator import iter_documents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/pilot/pilot-0.1.jsonl"))
    parser.add_argument("--split", type=Path, default=Path("data/splits/pilot-0.1.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260812)
    args = parser.parse_args()

    cases = {document["case_id"]: document for _, document in iter_documents(args.data)}
    split_manifest = json.loads(args.split.read_text(encoding="utf-8"))
    split_cases = {
        name: [cases[case_id] for case_id in details["case_ids"]]
        for name, details in split_manifest["splits"].items()
    }
    report = write_run(
        args.output,
        split_cases["train"],
        {"validation": split_cases["validation"], "test": split_cases["test"]},
        Path("configs"),
        args.seed,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
