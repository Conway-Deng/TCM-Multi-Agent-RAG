from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator
import xml.etree.ElementTree as ET
from zipfile import ZipFile


_SHEET_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    if not letters:
        return 0
    value = 0
    for char in letters.group(0):
        value = value * 26 + ord(char) - 64
    return value - 1


def _xlsx_rows(path: Path) -> Iterator[dict[str, Any]]:
    with ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.findall(".//m:t", _SHEET_NS)) for item in root.findall("m:si", _SHEET_NS)]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        for sheet in workbook.findall("m:sheets/m:sheet", _SHEET_NS):
            target = targets[sheet.attrib[_REL_ID]].lstrip("/")
            if not target.startswith("xl/"):
                target = f"xl/{target}"
            root = ET.fromstring(archive.read(target))
            rows = root.findall(".//m:sheetData/m:row", _SHEET_NS)
            headers: list[str] = []
            for row_index, row in enumerate(rows):
                values: dict[int, str] = {}
                for cell in row.findall("m:c", _SHEET_NS):
                    index = _column_index(cell.attrib.get("r", "A1"))
                    value_node = cell.find("m:v", _SHEET_NS)
                    inline = cell.find("m:is", _SHEET_NS)
                    if inline is not None:
                        value = "".join(node.text or "" for node in inline.findall(".//m:t", _SHEET_NS))
                    else:
                        value = "" if value_node is None else value_node.text or ""
                        if cell.attrib.get("t") == "s" and value:
                            value = shared[int(value)]
                    values[index] = value
                width = max(values, default=-1) + 1
                ordered = [values.get(index, "") for index in range(width)]
                if row_index == 0:
                    headers = [str(value).strip() or f"column_{index + 1}" for index, value in enumerate(ordered)]
                    continue
                if len(ordered) < len(headers):
                    ordered.extend([""] * (len(headers) - len(ordered)))
                record = {header: ordered[index] if index < len(ordered) else "" for index, header in enumerate(headers)}
                record["__sheet__"] = sheet.attrib.get("name", "")
                record["__row__"] = row_index + 1
                yield record


def read_tabular(path: Path) -> Iterator[dict[str, Any]]:
    suffix = path.suffix.casefold()
    if suffix == ".xlsx":
        yield from _xlsx_rows(path)
        return
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        with path.open(newline="", encoding="utf-8-sig") as handle:
            yield from csv.DictReader(handle, delimiter=delimiter)
        return
    if suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, dict):
                yield item
        return
    if suffix == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    yield item
        return
    if suffix in {".sqlite", ".sqlite3", ".db"}:
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as connection:
            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            for table in tables:
                safe_table = table.replace('"', '""')
                cursor = connection.execute(f'SELECT * FROM "{safe_table}"')
                columns = [item[0] for item in cursor.description]
                for row in cursor:
                    yield {**dict(zip(columns, row)), "__table__": table}
        return
    raise ValueError(f"Unsupported source format: {path.suffix}")
