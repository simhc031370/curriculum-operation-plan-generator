"""업로드된 HWPX 원본 서식에 내용을 그대로 채워 다시 포장한다."""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

LOCKED_COL_KEYWORDS = (
    "월",
    "주",
    "기간",
    "공휴일",
    "학교행사",
    "학교 행사",
)

PLACEHOLDER_RE = re.compile(
    r"(OO|O\s*O|○○|◯|○|□|_{2,}|\(\s*\)|미정)",
    re.I,
)


def _local(tag: str) -> str:
    if not tag:
        return ""
    if "}" in tag:
        return tag.rsplit("}", 1)[-1].lower()
    if ":" in tag:
        return tag.split(":", 1)[-1].lower()
    return tag.lower()


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").lower())


@dataclass
class HwpxSlot:
    id: str
    section: str
    kind: str  # cell | para
    table_index: int | None
    row: int | None
    col: int | None
    col_header: str
    current_text: str
    locked: bool
    hint: str = ""


def _cell_text(tc: etree._Element) -> str:
    parts: list[str] = []
    for t in tc.iter():
        if _local(t.tag) == "t" and t.text:
            parts.append(t.text)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _set_cell_text(tc: etree._Element, text: str) -> None:
    t_nodes = [el for el in tc.iter() if _local(el.tag) == "t"]
    if not t_nodes:
        return
    t_nodes[0].text = text
    for extra in t_nodes[1:]:
        extra.text = None


def _para_text(p: etree._Element) -> str:
    parts: list[str] = []
    for t in p.iter():
        if _local(t.tag) == "t" and t.text:
            parts.append(t.text)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _set_para_text(p: etree._Element, text: str) -> None:
    t_nodes = [el for el in p.iter() if _local(el.tag) == "t"]
    if not t_nodes:
        return
    t_nodes[0].text = text
    for extra in t_nodes[1:]:
        extra.text = None


def _inside_table(el: etree._Element) -> bool:
    cur = el.getparent()
    while cur is not None:
        if _local(cur.tag) in {"tbl", "tc"}:
            return True
        cur = cur.getparent()
    return False


def _is_locked_col(header: str) -> bool:
    h = _norm(header)
    return any(_norm(k) in h for k in LOCKED_COL_KEYWORDS)


def _should_fill_cell(text: str, col_header: str, row: int) -> bool:
    if PLACEHOLDER_RE.search(text or ""):
        return True
    if row == 0:
        return False
    if _is_locked_col(col_header):
        return False
    return not bool(text)


def _should_fill_para(text: str) -> bool:
    if not text:
        return True
    if re.fullmatch(r"[가-하]\.?", text):
        return True
    if PLACEHOLDER_RE.search(text):
        return True
    return len(text) <= 2


def extract_slots(hwpx_path: str | Path) -> list[HwpxSlot]:
    path = Path(hwpx_path)
    slots: list[HwpxSlot] = []
    with zipfile.ZipFile(path, "r") as zf:
        section_names = sorted(
            n
            for n in zf.namelist()
            if re.search(r"(^|/)section\d+\.xml$", n, re.I)
        )
        for section_name in section_names:
            root = etree.fromstring(zf.read(section_name))
            table_i = 0
            for elem in root.iter():
                if _local(elem.tag) != "tbl":
                    continue
                rows = [tr for tr in list(elem) if _local(tr.tag) == "tr"]
                headers: list[str] = []
                if rows:
                    headers = [
                        _cell_text(tc)
                        for tc in list(rows[0])
                        if _local(tc.tag) == "tc"
                    ]
                for r_idx, tr in enumerate(rows):
                    cells = [tc for tc in list(tr) if _local(tc.tag) == "tc"]
                    for c_idx, tc in enumerate(cells):
                        text = _cell_text(tc)
                        header = headers[c_idx] if c_idx < len(headers) else ""
                        fill = _should_fill_cell(text, header, r_idx)
                        slots.append(
                            HwpxSlot(
                                id=f"{section_name}|t{table_i}|r{r_idx}|c{c_idx}",
                                section=section_name,
                                kind="cell",
                                table_index=table_i,
                                row=r_idx,
                                col=c_idx,
                                col_header=header,
                                current_text=text,
                                locked=not fill,
                                hint=f"표{table_i+1} {header or f'열{c_idx+1}'}",
                            )
                        )
                table_i += 1

            para_i = 0
            for elem in root.iter():
                if _local(elem.tag) != "p":
                    continue
                if _inside_table(elem):
                    continue
                if any(_local(x.tag) == "tbl" for x in elem.iter() if x is not elem):
                    continue
                text = _para_text(elem)
                if not _should_fill_para(text) and text:
                    continue
                slots.append(
                    HwpxSlot(
                        id=f"{section_name}|p{para_i}",
                        section=section_name,
                        kind="para",
                        table_index=None,
                        row=None,
                        col=None,
                        col_header="",
                        current_text=text,
                        locked=False,
                        hint="문단",
                    )
                )
                para_i += 1
    return slots


def slots_for_prompt(slots: list[HwpxSlot], *, limit: int = 220) -> str:
    fillable = [s for s in slots if not s.locked][:limit]
    payload = [
        {
            "id": s.id,
            "kind": s.kind,
            "header": s.col_header,
            "hint": s.hint,
            "current": s.current_text,
        }
        for s in fillable
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def apply_fills(hwpx_path: str | Path, fills: dict[str, str]) -> bytes:
    path = Path(hwpx_path)
    by_section: dict[str, dict[str, str]] = {}
    for slot_id, value in fills.items():
        if "|" not in slot_id:
            continue
        section = slot_id.split("|", 1)[0]
        by_section.setdefault(section, {})[slot_id] = value

    buf = io.BytesIO()
    with zipfile.ZipFile(path, "r") as zin, zipfile.ZipFile(buf, "w") as zout:
        if "mimetype" in zin.namelist():
            zout.writestr(
                "mimetype",
                zin.read("mimetype"),
                compress_type=zipfile.ZIP_STORED,
            )

        for item in zin.infolist():
            if item.filename == "mimetype":
                continue
            data = zin.read(item.filename)
            if item.filename in by_section:
                data = _apply_section_fills(data, item.filename, by_section[item.filename])
            compress = (
                zipfile.ZIP_STORED
                if item.compress_type == zipfile.ZIP_STORED
                else zipfile.ZIP_DEFLATED
            )
            zout.writestr(item.filename, data, compress_type=compress)
    return buf.getvalue()


def _apply_section_fills(
    xml_bytes: bytes, section_name: str, fills: dict[str, str]
) -> bytes:
    parser = etree.XMLParser(remove_blank_text=False)
    root = etree.fromstring(xml_bytes, parser=parser)

    table_i = 0
    for elem in root.iter():
        if _local(elem.tag) != "tbl":
            continue
        rows = [tr for tr in list(elem) if _local(tr.tag) == "tr"]
        for r_idx, tr in enumerate(rows):
            cells = [tc for tc in list(tr) if _local(tc.tag) == "tc"]
            for c_idx, tc in enumerate(cells):
                slot_id = f"{section_name}|t{table_i}|r{r_idx}|c{c_idx}"
                if slot_id in fills:
                    _set_cell_text(tc, str(fills[slot_id]))
        table_i += 1

    para_i = 0
    for elem in root.iter():
        if _local(elem.tag) != "p":
            continue
        if _inside_table(elem):
            continue
        if any(_local(x.tag) == "tbl" for x in elem.iter() if x is not elem):
            continue
        text = _para_text(elem)
        if not _should_fill_para(text) and text:
            continue
        slot_id = f"{section_name}|p{para_i}"
        if slot_id in fills:
            _set_para_text(elem, str(fills[slot_id]))
        para_i += 1

    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=None,
    )


def parse_fills_json(raw: str) -> dict[str, str]:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("슬롯 채움 JSON을 찾지 못했습니다.")
    obj = json.loads(text[start : end + 1])
    if isinstance(obj, dict) and isinstance(obj.get("fills"), dict):
        obj = obj["fills"]
    if not isinstance(obj, dict):
        raise ValueError("슬롯 채움 JSON 형식이 올바르지 않습니다.")
    return {str(k): str(v).strip() for k, v in obj.items() if v is not None}


def slots_summary(slots: list[HwpxSlot]) -> dict[str, int]:
    return {
        "total": len(slots),
        "fillable": sum(1 for s in slots if not s.locked),
        "locked": sum(1 for s in slots if s.locked),
    }
