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

OO_RE = re.compile(r"O\s*O|OO")
CIRCLE_RE = re.compile(r"[○◯]")
PLACEHOLDER_RE = re.compile(
    r"(OO|O\s*O|○○|◯|○|□|_{2,})",
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
    """레이아웃용 빈 문단은 건드리지 않는다. 가./나. 또는 OO 자리만 채움."""
    s = (text or "").strip()
    if re.fullmatch(r"[가-하]\.?", s):
        return True
    if s and (OO_RE.search(s) or CIRCLE_RE.search(s)):
        return True
    return False


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
                if not _should_fill_para(text):
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


def _replace_markers(
    text: str,
    *,
    subject: str,
    written_exam_count: int,
    written_exam_ratio: int,
    performance_exam_count: int,
    performance_exam_ratio: int,
) -> str:
    """OO → 과목, ○%/○회 → 입력 비율·횟수. 과목명으로 ○를 덮어쓰지 않는다."""
    t = text
    t = OO_RE.sub(subject, t)

    # 문맥별 ○% / ○회
    if "수행" in t:
        t = re.sub(r"[○◯]\s*%", f"{performance_exam_ratio}%", t)
        t = re.sub(r"[○◯]\s*회", f"{performance_exam_count}회", t)
    if "정기" in t or "지필" in t or "1차" in t or "2차" in t:
        # 1차/2차 분할
        if "1차" in t and written_exam_count >= 1:
            share = written_exam_ratio if written_exam_count == 1 else max(
                written_exam_ratio // 2, 1
            )
            t = re.sub(r"[○◯]\s*%", f"{share}%", t)
        elif "2차" in t:
            share = 0 if written_exam_count <= 1 else written_exam_ratio - (
                written_exam_ratio // 2
            )
            t = re.sub(r"[○◯]\s*%", f"{share}%", t)
        else:
            t = re.sub(r"[○◯]\s*%", f"{written_exam_ratio}%", t)
        t = re.sub(r"[○◯]\s*회", f"{written_exam_count}회", t)

    # 남은 ○% 는 과목으로 치환하지 말고 비율만 보정
    t = re.sub(r"[○◯]\s*%", f"{written_exam_ratio}%", t)
    t = re.sub(r"[○◯]\s*회", f"{performance_exam_count}회", t)
    # 단독 ○ 잔여만 제거(과목 치환 금지)
    t = CIRCLE_RE.sub("", t)
    return re.sub(r"\s{2,}", " ", t).strip()


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
    """안전하게 확정 가능한 칸만 채운다. 달력 본문·레이아웃 빈칸은 건드리지 않는다."""
    _ = (school_level, total_hours, unit_names, performance_items)  # LLM 상세 채움용
    fills: dict[str, str] = {}

    purpose = {
        "가": f"가. {subject} 교과의 성취기준에 따른 학업성취도를 정확하게 평가한다.",
        "나": f"나. 학습 과정을 확인하고 피드백하여 학생의 성장을 지원한다.",
        "다": f"다. 평가 결과를 수업 개선과 개별 맞춤 지도에 활용한다.",
    }

    for s in slots:
        if s.locked:
            continue
        header = s.col_header or ""
        cur = (s.current_text or "").strip()

        # 1) OO / ○ 자리표시가 있는 칸만 문맥에 맞게 치환
        if cur and (OO_RE.search(cur) or CIRCLE_RE.search(cur)):
            fills[s.id] = _replace_markers(
                cur,
                subject=subject,
                written_exam_count=written_exam_count,
                written_exam_ratio=written_exam_ratio,
                performance_exam_count=performance_exam_count,
                performance_exam_ratio=performance_exam_ratio,
            )
            continue

        # 2) 표지 메타 정보
        if not cur:
            if header.strip() == "학년" or (
                "학년" in header and "학기" not in header and len(header) <= 6
            ):
                fills[s.id] = grade
            elif header.strip() == "과목" or header.strip() == "교과":
                fills[s.id] = subject
            continue

        # 3) 평가 목적 가/나/다
        if s.kind == "para":
            m = re.fullmatch(r"([가-하])\.?", cur)
            if m and m.group(1) in purpose:
                fills[s.id] = purpose[m.group(1)]

    return {k: v for k, v in fills.items() if v and str(v).strip()}


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
        if not _should_fill_para(text):
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
