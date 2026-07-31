"""업로드된 HWPX 원본 서식에 내용을 그대로 채워 다시 포장한다."""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

HP_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"

LOCKED_COL_KEYWORDS = (
    "월",
    "주",
    "기간",
    "공휴일",
    "학교행사",
    "학교 행사",
)

PLACEHOLDER_RE = re.compile(
    r"(OO|O\s*O|○○|◯|○|□|_{2,}|\(\s*\))",
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


def _qname(local: str) -> str:
    return f"{{{HP_NS}}}{local}"


def _cell_text(tc: etree._Element) -> str:
    parts: list[str] = []
    for t in tc.iter():
        if _local(t.tag) == "t" and t.text:
            parts.append(t.text)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _ensure_t_node(parent_run: etree._Element) -> etree._Element:
    for child in parent_run:
        if _local(child.tag) == "t":
            return child
    return etree.SubElement(parent_run, _qname("t"))


def _set_cell_text(tc: etree._Element, text: str) -> bool:
    """셀에 텍스트를 기록한다. 빈 셀(run만 있는 경우)도 처리. 성공 여부 반환."""
    value = text if text is not None else ""
    t_nodes = [el for el in tc.iter() if _local(el.tag) == "t"]
    if t_nodes:
        t_nodes[0].text = value
        for extra in t_nodes[1:]:
            extra.text = None
        return True

    # 빈 셀: <hp:run .../> 만 있는 경우가 많음 → run 안에 t 추가
    runs = [el for el in tc.iter() if _local(el.tag) == "run"]
    if runs:
        t = _ensure_t_node(runs[0])
        t.text = value
        return True

    # run조차 없으면 subList/p/run/t 생성
    sublists = [el for el in tc.iter() if _local(el.tag) == "sublist"]
    sub = sublists[0] if sublists else etree.SubElement(tc, _qname("subList"))
    paras = [el for el in sub if _local(el.tag) == "p"]
    if paras:
        p = paras[0]
    else:
        p = etree.SubElement(sub, _qname("p"))
        p.set("paraPrIDRef", "0")
        p.set("styleIDRef", "0")
        p.set("pageBreak", "0")
        p.set("columnBreak", "0")
        p.set("merged", "0")
    run = etree.SubElement(p, _qname("run"))
    run.set("charPrIDRef", "0")
    t = etree.SubElement(run, _qname("t"))
    t.text = value
    return True


def _para_text(p: etree._Element) -> str:
    parts: list[str] = []
    for t in p.iter():
        if _local(t.tag) == "t" and t.text:
            parts.append(t.text)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _set_para_text(p: etree._Element, text: str) -> bool:
    value = text if text is not None else ""
    t_nodes = [el for el in p.iter() if _local(el.tag) == "t"]
    if t_nodes:
        t_nodes[0].text = value
        for extra in t_nodes[1:]:
            extra.text = None
        return True
    runs = [el for el in p.iter() if _local(el.tag) == "run"]
    if runs:
        # ctrl/secPr만 있는 run은 피하고 텍스트용 run 사용
        for run in runs:
            if any(_local(c.tag) in {"secpr", "ctrl", "tbl"} for c in run):
                continue
            t = _ensure_t_node(run)
            t.text = value
            return True
        t = _ensure_t_node(runs[-1])
        t.text = value
        return True
    run = etree.SubElement(p, _qname("run"))
    run.set("charPrIDRef", "0")
    t = etree.SubElement(run, _qname("t"))
    t.text = value
    return True


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


def build_baseline_fills(
    slots: list[HwpxSlot],
    *,
    school_level: str,
    grade: str,
    subject: str,
    total_hours: int,
    unit_names: str,
    performance_items: str,
    written_exam_count: int,
    written_exam_ratio: int,
    performance_exam_count: int,
    performance_exam_ratio: int,
) -> dict[str, str]:
    """LLM 실패/누락에도 핵심 칸이 비지 않도록 규칙 기반 기본값을 채운다."""
    units = [ln.strip(" -\t") for ln in unit_names.splitlines() if ln.strip()]
    if len(units) <= 1 and unit_names.strip():
        units = [p.strip() for p in re.split(r"[,/|]", unit_names) if p.strip()]
    perfs = [ln.strip(" -\t") for ln in performance_items.splitlines() if ln.strip()]
    if len(perfs) <= 1 and performance_items.strip():
        perfs = [p.strip() for p in re.split(r"[,/|]", performance_items) if p.strip()]

    fills: dict[str, str] = {}
    unit_i = 0
    perf_i = 0
    hours_left = total_hours

    for s in slots:
        if s.locked:
            continue
        header = s.col_header or ""
        cur = s.current_text or ""
        hnorm = _norm(header)

        # OO 자리표시 → 과목
        if PLACEHOLDER_RE.search(cur):
            fills[s.id] = PLACEHOLDER_RE.sub(subject, cur)
            continue

        if not cur:
            if "학년" in header and "학기" not in header:
                fills[s.id] = grade
            elif "과목" in header:
                fills[s.id] = subject
            elif "학교" in header and "행사" not in header:
                fills[s.id] = ""  # 학교명은 원본 유지(금당중 등) — 빈 칸만
            elif "단원" in header:
                if unit_i < len(units):
                    fills[s.id] = units[unit_i]
                    unit_i += 1
            elif "성취기준" in header:
                fills[s.id] = "(공식 성취기준 반영)"
            elif "시수" in header or "누계" in header:
                if hours_left > 0:
                    chunk = 1 if hours_left >= 1 else hours_left
                    fills[s.id] = str(chunk)
                    hours_left -= chunk
            elif "수업" in header and "방법" in header:
                fills[s.id] = "강의·실습"
            elif "주안점" in header or "연계" in header:
                fills[s.id] = "수업-평가 연계"
            elif "영역명" in header or (s.kind == "cell" and "수행" in header):
                if perf_i < len(perfs):
                    fills[s.id] = perfs[perf_i]
                    perf_i += 1
            elif "반영비율" in hnorm or "반영" in header:
                # 평가비율 표의 빈 칸 — 문맥에 따라
                if "정기" in header or "지필" in header:
                    fills[s.id] = f"{written_exam_ratio}%"
                elif "수행" in header:
                    fills[s.id] = f"{performance_exam_ratio}%"
            elif s.kind == "para" and re.fullmatch(r"[가-하]\.?", cur or "") or (
                s.kind == "para" and not cur
            ):
                # 빈 목적/개요 문단
                if not cur or re.fullmatch(r"[가-하]\.?", cur):
                    prefix = f"{cur} " if cur else ""
                    fills[s.id] = (
                        f"{prefix}{school_level} {grade} {subject} 교과의 "
                        f"교수·학습·평가를 체계적으로 운영한다."
                    )

    # 제목/헤더성 OO 치환은 위에서 처리됨
    return {k: v for k, v in fills.items() if v is not None and str(v).strip() != ""}


def apply_fills(hwpx_path: str | Path, fills: dict[str, str]) -> tuple[bytes, int]:
    """원본 HWPX에 fills를 적용. (bytes, 실제 기록된 칸 수) 반환."""
    path = Path(hwpx_path)
    by_section: dict[str, dict[str, str]] = {}
    for slot_id, value in fills.items():
        if "|" not in slot_id:
            continue
        if value is None or str(value).strip() == "":
            continue
        section = slot_id.split("|", 1)[0]
        by_section.setdefault(section, {})[slot_id] = str(value)

    applied = 0
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
                data, n = _apply_section_fills(
                    data, item.filename, by_section[item.filename]
                )
                applied += n
            compress = (
                zipfile.ZIP_STORED
                if item.compress_type == zipfile.ZIP_STORED
                else zipfile.ZIP_DEFLATED
            )
            zout.writestr(item.filename, data, compress_type=compress)
    return buf.getvalue(), applied


def _apply_section_fills(
    xml_bytes: bytes, section_name: str, fills: dict[str, str]
) -> tuple[bytes, int]:
    parser = etree.XMLParser(remove_blank_text=False)
    root = etree.fromstring(xml_bytes, parser=parser)
    applied = 0

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
                    if _set_cell_text(tc, str(fills[slot_id])):
                        applied += 1
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
            if _set_para_text(elem, str(fills[slot_id])):
                applied += 1
        para_i += 1

    out = etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=None,
    )
    return out, applied


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
    return {
        str(k): str(v).strip()
        for k, v in obj.items()
        if v is not None and str(v).strip() != ""
    }


def slots_summary(slots: list[HwpxSlot]) -> dict[str, int]:
    return {
        "total": len(slots),
        "fillable": sum(1 for s in slots if not s.locked),
        "locked": sum(1 for s in slots if s.locked),
    }
