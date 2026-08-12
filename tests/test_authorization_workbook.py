import csv
import json
import zipfile
from pathlib import Path

import pytest

from mcpmodel.authorization_reconstruction import REVIEW_FIELDS
from mcpmodel.authorization_workbook import (
    compare_authorization_reviews,
    import_easy_authorization_workbook,
)


def _sheet_xml(cells: dict[str, object]) -> str:
    rendered = []
    for reference, value in cells.items():
        text = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        rendered.append(f'<c r="{reference}" t="inlineStr"><is><t>{text}</t></is></c>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData><row>{''.join(rendered)}</row></sheetData></worksheet>"
    )


def _workbook(path: Path, draft: dict, reviewer: str = "reviewer_alice") -> None:
    names = ["填写说明", "授权内容", "证据依据", "内部校验（勿改）"]
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        + "".join(
            f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>'
            for index, name in enumerate(names, start=1)
        )
        + "</sheets></workbook>"
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{index}" Target="worksheets/sheet{index}.xml" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
            for index in range(1, 5)
        )
        + "</Relationships>"
    )
    basis = "合理必需(task_implied)"
    sheets = [
        {"A1": "MCPModel 授权复核 A（易填版）", "B4": reviewer},
        {
            "A4": "场景1",
            "B4": draft["task_evidence"]["user_task"],
            "C4": "纳入",
            "D4": "external_agent",
            "E4": "http",
            "F4": "read",
            "G4": "https://example.test/status",
            "H4": "无外发",
            "I4": "30",
            "J4": "3",
            "K4": "check status",
            "L4": "只读，不允许修改。",
        },
        {"A4": "场景1", **{f"{column}4": basis for column in "BCDEFGH"}},
        {
            "A4": "场景1",
            "B4": draft["draft_id"],
            "C4": draft["scenario_group"],
            "D4": draft["task_evidence"]["sha256"],
            "E4": draft["candidate_count"],
            "F4": draft["task_evidence"]["user_task"],
        },
    ]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        for index, cells in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(cells))


def _draft(tmp_path: Path) -> tuple[Path, dict]:
    task = "please check status at https://example.test/status"
    import hashlib

    draft = {
        "draft_id": "authdraft_1234567890abcdef",
        "scenario_group": "group_001",
        "candidate_count": 1,
        "task_evidence": {"user_task": task, "sha256": hashlib.sha256(task.encode()).hexdigest()},
    }
    path = tmp_path / "drafts.jsonl"
    path.write_text(json.dumps(draft) + "\n", encoding="utf-8")
    return path, draft


def test_easy_workbook_imports_to_canonical_csv(tmp_path) -> None:
    drafts, draft = _draft(tmp_path)
    workbook = tmp_path / "A.xlsx"
    _workbook(workbook, draft)
    output = tmp_path / "review-A.csv"
    summary = import_easy_authorization_workbook(
        workbook, drafts, output, expected_reviewer="A"
    )
    with output.open(encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert summary["included_count"] == 1
    assert row["tools_json"] == '["http"]'
    assert row["sinks_json"] == '["<none>"]'
    assert row["valid_until"] == "2026-08-12T00:30:00Z"


def test_easy_workbook_rejects_blank_reviewer(tmp_path) -> None:
    drafts, draft = _draft(tmp_path)
    workbook = tmp_path / "A.xlsx"
    _workbook(workbook, draft, reviewer="")
    with pytest.raises(ValueError, match="复核员代号不能为空"):
        import_easy_authorization_workbook(
            workbook, drafts, tmp_path / "review.csv", expected_reviewer="A"
        )


def _review_csv(path: Path, reviewer: str, decision: str, max_calls: str = "3") -> None:
    row = {field: "" for field in REVIEW_FIELDS}
    row.update(
        {
            "draft_id": "authdraft_1234567890abcdef",
            "scenario_group": "group_001",
            "task_sha256": "a" * 64,
            "reviewer_id": reviewer,
            "decision": decision,
            "subject": "external_agent",
            "tools_json": '["http"]',
            "actions_json": '["read"]',
            "resources_json": '["https://example.test/status"]',
            "sinks_json": '["<none>"]',
            "valid_from": "2026-08-12T00:00:00Z",
            "valid_until": "2026-08-12T00:30:00Z",
            "max_calls": max_calls,
            **{f"{name}_basis": "task_implied" for name in (
                "subject", "tools", "actions", "resources", "sinks", "temporal", "cardinality"
            )},
        }
    )
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerow(row)


def test_comparison_creates_queue_for_decision_disagreement(tmp_path) -> None:
    left, right = tmp_path / "A.csv", tmp_path / "B.csv"
    _review_csv(left, "alice", "include")
    _review_csv(right, "bob", "exclude")
    result = compare_authorization_reviews(left, right, tmp_path / "adjudication.csv")
    assert result["disagreement_count"] == 1
    assert result["items"][0]["status"] == "decision_disagreement"


def test_comparison_rejects_same_reviewer(tmp_path) -> None:
    left, right = tmp_path / "A.csv", tmp_path / "B.csv"
    _review_csv(left, "alice", "include")
    _review_csv(right, "alice", "include")
    with pytest.raises(ValueError, match="different people"):
        compare_authorization_reviews(left, right, tmp_path / "adjudication.csv")
