import csv

from mcpmodel.annotation import create_annotation_pack, validate_annotation_sheet
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
