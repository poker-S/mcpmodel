#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from mcpmodel.selective import split_validation_roles, write_selective_run
from mcpmodel.validator import iter_documents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/pilot/pilot-0.1.jsonl"))
    parser.add_argument("--split", type=Path, default=Path("data/splits/pilot-0.1.json"))
    parser.add_argument(
        "--config", type=Path, default=Path("configs/selective_pipeline.yaml")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cases = {document["case_id"]: document for _, document in iter_documents(args.data)}
    split_manifest = json.loads(args.split.read_text(encoding="utf-8"))
    split_cases = {
        name: [cases[case_id] for case_id in details["case_ids"]]
        for name, details in split_manifest["splits"].items()
    }
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    probability_cases, conformal_cases = split_validation_roles(
        split_cases["validation"],
        probability_calibration_groups=config["probability_calibration_groups"],
        conformal_calibration_groups=config["conformal_calibration_groups"],
    )
    report = write_selective_run(
        args.output,
        train_cases=split_cases["train"],
        probability_calibration_cases=probability_cases,
        conformal_calibration_cases=conformal_cases,
        test_cases=split_cases["test"],
        config_dir=Path("configs"),
        seed=int(config["seed"]),
        alpha=float(config["alpha"]),
        repository_root=Path.cwd(),
        input_artifacts={"data": args.data, "split": args.split},
        config_artifacts={
            "selective_pipeline.yaml": args.config,
            "hard_rules.yaml": Path("configs/hard_rules.yaml"),
            "resource_labels.yaml": Path("configs/resource_labels.yaml"),
            "tool_normalization.yaml": Path("configs/tool_normalization.yaml"),
        },
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
