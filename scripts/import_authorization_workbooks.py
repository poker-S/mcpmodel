#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from mcpmodel.authorization_workbook import (
    compare_authorization_reviews,
    import_easy_authorization_workbook,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--reviewer-a", type=Path, required=True)
    parser.add_argument("--reviewer-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    drafts_source = args.pack / "authorization-drafts.jsonl"
    drafts_output = args.output / "authorization-drafts.jsonl"
    shutil.copyfile(drafts_source, drafts_output)
    summary_a = import_easy_authorization_workbook(
        args.reviewer_a,
        drafts_output,
        args.output / "authorization-review-A.csv",
        expected_reviewer="A",
    )
    summary_b = import_easy_authorization_workbook(
        args.reviewer_b,
        drafts_output,
        args.output / "authorization-review-B.csv",
        expected_reviewer="B",
    )
    comparison = compare_authorization_reviews(
        args.output / "authorization-review-A.csv",
        args.output / "authorization-review-B.csv",
        args.output / "authorization-adjudication.csv",
    )
    manifest = {
        "schema_version": "0.1.0",
        "source_pack_drafts_sha256": _digest(drafts_source),
        "reviewer_a_workbook_sha256": _digest(args.reviewer_a),
        "reviewer_b_workbook_sha256": _digest(args.reviewer_b),
        "reviewer_a": summary_a,
        "reviewer_b": summary_b,
        "comparison": comparison,
    }
    (args.output / "workbook-import-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
