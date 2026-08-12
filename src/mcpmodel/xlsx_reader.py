"""Small read-only XLSX reader for fixed annotation templates.

It deliberately supports only cell values. It never evaluates formulas, macros, links,
or embedded objects, and it never extracts archive members to disk.
"""

from __future__ import annotations

import posixpath
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
DOC_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
MAX_ARCHIVE_MEMBERS = 500
MAX_MEMBER_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 80 * 1024 * 1024


class WorkbookReadError(ValueError):
    """Raised when a review workbook is malformed or exceeds safe read limits."""


def _xml(archive: zipfile.ZipFile, name: str) -> ET.Element:
    try:
        info = archive.getinfo(name)
    except KeyError as exc:
        raise WorkbookReadError(f"missing XLSX member: {name}") from exc
    if info.file_size > MAX_MEMBER_BYTES:
        raise WorkbookReadError(f"XLSX member too large: {name}")
    return ET.fromstring(archive.read(info))


def _validate_archive(archive: zipfile.ZipFile) -> None:
    infos = archive.infolist()
    if len(infos) > MAX_ARCHIVE_MEMBERS:
        raise WorkbookReadError("XLSX contains too many archive members")
    if sum(info.file_size for info in infos) > MAX_TOTAL_BYTES:
        raise WorkbookReadError("XLSX uncompressed size exceeds the read limit")
    for info in infos:
        normalized = posixpath.normpath(info.filename.replace("\\", "/"))
        if normalized.startswith("../") or normalized.startswith("/"):
            raise WorkbookReadError(f"unsafe XLSX member path: {info.filename}")


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = _xml(archive, "xl/sharedStrings.xml")
    return ["".join(node.text or "" for node in item.findall(".//x:t", NS)) for item in root]


def _column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha()).upper()
    value = 0
    for character in letters:
        value = value * 26 + ord(character) - 64
    return value - 1


def _cell_value(cell: ET.Element, shared: list[str]) -> object:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//x:t", NS))
    value_node = cell.find("x:v", NS)
    if value_node is None or value_node.text is None:
        return ""
    value = value_node.text
    if cell_type == "s":
        try:
            return shared[int(value)]
        except (IndexError, ValueError) as exc:
            raise WorkbookReadError("invalid shared-string reference") from exc
    if cell_type in {"str", "e"}:
        return value
    if cell_type == "b":
        return value == "1"
    try:
        number = float(value)
    except ValueError:
        return value
    return int(number) if number.is_integer() else number


def read_xlsx_values(path: Path) -> dict[str, list[list[object]]]:
    """Return sheet values while ignoring formulas, macros, links, and drawings."""
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise WorkbookReadError(f"not a valid XLSX file: {path}") from exc
    with archive:
        _validate_archive(archive)
        workbook = _xml(archive, "xl/workbook.xml")
        relationships = _xml(archive, "xl/_rels/workbook.xml.rels")
        targets = {
            relationship.attrib["Id"]: relationship.attrib["Target"]
            for relationship in relationships.findall("r:Relationship", REL_NS)
        }
        shared = _shared_strings(archive)
        result: dict[str, list[list[object]]] = {}
        for sheet in workbook.findall(".//x:sheets/x:sheet", NS):
            name = sheet.attrib["name"]
            relationship_id = sheet.attrib.get(DOC_REL)
            if relationship_id not in targets:
                raise WorkbookReadError(f"missing relationship for worksheet: {name}")
            target = targets[relationship_id]
            if target.startswith("/xl/"):
                member = posixpath.normpath(target.lstrip("/"))
            elif target.startswith("/"):
                raise WorkbookReadError(f"unsafe worksheet target: {target}")
            else:
                member = posixpath.normpath(posixpath.join("xl", target))
            if not member.startswith("xl/"):
                raise WorkbookReadError(f"unsafe worksheet target: {target}")
            root = _xml(archive, member)
            cells: dict[tuple[int, int], object] = {}
            max_row = max_column = -1
            for cell in root.findall(".//x:sheetData/x:row/x:c", NS):
                reference = cell.attrib.get("r", "")
                digits = "".join(character for character in reference if character.isdigit())
                if not digits:
                    continue
                row = int(digits) - 1
                column = _column_index(reference)
                cells[(row, column)] = _cell_value(cell, shared)
                max_row, max_column = max(max_row, row), max(max_column, column)
            matrix = [
                [cells.get((row, column), "") for column in range(max_column + 1)]
                for row in range(max_row + 1)
            ]
            result[name] = matrix
        return result
