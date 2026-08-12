import csv
import json

from mcpmodel.annotation import (
    agreement_report,
    create_annotation_pack,
    finalize_human_labels,
    validate_annotation_sheet,
    write_adjudication_queue,
)
from mcpmodel.pilot import generate_pilot


def test_annotation_pack_hides_labels(tmp_path) -> None:
    cases = generate_pilot()
    summary = create_annotation_pack(cases, tmp_path / "pack")
    contexts = (tmp_path / "pack" / "contexts.jsonl").read_text(encoding="utf-8")
    assert '"labels"' not in contexts
    assert summary["case_count"] == 30


def test_completed_annotation_sheet_validates(tmp_path) -> None:
    cases = generate_pilot()
    create_annotation_pack(cases, tmp_path / "pack", ("A",))
    path = tmp_path / "pack" / "labels-A.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row.update(
            {
                "inherent_risk": "L2",
                "recommended_action": "approve",
                "tool_scope": "0",
                "action_scope": "0",
                "resource_scope": "0.5",
                "sink_scope": "0",
                "temporal_scope": "0",
                "subject_scope": "0",
            }
        )
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    assert validate_annotation_sheet(path, {case["case_id"] for case in cases}) == []


def _complete(path, risks: list[str], actions: list[str]) -> None:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row, risk, action in zip(rows, risks, actions, strict=True):
        row.update(
            {
                "inherent_risk": risk,
                "recommended_action": action,
                "tool_scope": "0",
                "action_scope": "0",
                "resource_scope": "0",
                "sink_scope": "0",
                "temporal_scope": "0",
                "subject_scope": "0",
            }
        )
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def test_agreement_and_adjudication_pipeline(tmp_path) -> None:
    cases = generate_pilot()[:3]
    pack = tmp_path / "pack"
    create_annotation_pack(cases, pack)
    _complete(pack / "labels-A.csv", ["L0", "L2", "L4"], ["allow", "approve", "deny"])
    _complete(pack / "labels-B.csv", ["L0", "L3", "L4"], ["allow", "approve", "deny"])
    _complete(pack / "labels-C.csv", ["L0", "L2", "L4"], ["allow", "rewrite", "deny"])
    sheets = [pack / f"labels-{name}.csv" for name in "ABC"]
    report = agreement_report(sheets)
    assert report["disagreement_count"] == 1
    assert report["risk_unanimous_rate"] == 2 / 3
    assert report["risk_pairwise_qwk_mean"] > 0.9

    queue = tmp_path / "adjudication.csv"
    write_adjudication_queue(queue, report)
    with queue.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0].update(
        {
            "adjudicated_risk": "L2",
            "adjudicated_action": "approve",
            "reason_codes": "CONTEXT_INCOMPLETE",
            "adjudicator_id": "D",
            "adjudication_note": "复核授权边界后裁决",
        }
    )
    with queue.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    output = tmp_path / "human-labels.csv"
    summary = finalize_human_labels(sheets, queue, output)
    assert summary["case_count"] == 3
    assert summary["adjudicated_count"] == 1
    assert "CONTEXT_INCOMPLETE" in output.read_text(encoding="utf-8-sig")


def test_agreement_report_is_json_serializable(tmp_path) -> None:
    cases = generate_pilot()[:2]
    pack = tmp_path / "pack"
    create_annotation_pack(cases, pack)
    for name in "ABC":
        _complete(pack / f"labels-{name}.csv", ["L1", "L3"], ["allow", "approve"])
    report = agreement_report([pack / f"labels-{name}.csv" for name in "ABC"])
    json.dumps(report)
