"""업로드 문서에서 '채울 서식 골격'을 만든다.

제목·표 헤더·행 라벨은 고정하고, 내용 칸만 [작성]으로 비운다.
AI가 새 양식을 창작하지 못하도록 구조를 잠근다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TemplateSkeleton:
    skeleton_markdown: str
    locked_headings: list[str] = field(default_factory=list)
    locked_table_headers: list[str] = field(default_factory=list)
    source_char_count: int = 0


def _is_table_sep(line: str) -> bool:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells)


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _looks_like_row_label(cell: str) -> bool:
    text = cell.strip()
    if not text or text == "[작성]":
        return False
    if len(text) > 24:
        return False
    if re.fullmatch(r"\d+([./]\d+)*%?", text):
        return False
    # 짧은 구분/항목명은 라벨로 유지
    return True


def _blank_table(rows: list[list[str]]) -> tuple[list[list[str]], str | None]:
    if not rows:
        return rows, None
    header = rows[0]
    header_key = " | ".join(header)
    body = rows[1:]
    blanked: list[list[str]] = [header]
    for row in body:
        width = len(header)
        cells = (row + [""] * width)[:width]
        if cells and _looks_like_row_label(cells[0]):
            new_row = [cells[0]] + ["[작성]" for _ in cells[1:]]
        else:
            new_row = ["[작성]" for _ in cells]
        blanked.append(new_row)
    # 본문이 없으면 헤더만 있는 표 → 작성 행 2줄 확보
    if len(blanked) == 1:
        blanked.append(["[작성]" for _ in header])
        blanked.append(["[작성]" for _ in header])
    return blanked, header_key


def _rows_to_md(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    header = rows[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _normalize_heading(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _is_heading_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.startswith("#"):
        return True
    # 문장형 본문은 제목으로 보지 않음
    if re.search(r"(다|요|음|함|임|됨|함\.|다\.|요\.)$", s):
        return False
    if re.match(
        r"^(제?\s*\d+\s*[장절항]|[IVXLC]+\.|[0-9]+(\.[0-9]+)*\.?\s|[가-하]\.\s|[①-⑮]|\d+\))",
        s,
    ):
        return True
    # 키워드 제목: 짧고, 조사/서술어가 거의 없어야 함
    if (
        len(s) <= 28
        and " " not in s[:2]
        and not re.search(r"[은는이가을를에의사와과]", s)
        and any(
            k in s
            for k in (
                "계획",
                "평가",
                "기준",
                "시수",
                "단원",
                "목표",
                "방침",
                "운영",
                "성취",
                "성적",
                "세부",
                "총괄",
                "유의사항",
            )
        )
    ):
        return True
    return False


def _blank_paragraph(text: str) -> str:
    s = text.strip()
    if not s:
        return s
    # 짧은 라벨·제목은 유지
    if _is_heading_line(s) and len(s) <= 50:
        return s
    if len(s) <= 20:
        return s
    # 긴 본문은 슬롯으로 바꾸되, 원문 예시를 남겨 문체·길이를 맞추게 한다
    sample = s[:160].replace("\n", " ")
    return f"[작성: 원문예시「{sample}」를 새 입력 조건에 맞게 교체 작성]"


def build_template_skeleton(document_text: str) -> TemplateSkeleton:
    """원문에서 채움용 서식 골격을 생성한다."""
    raw = (document_text or "").replace("\r\n", "\n").strip()
    # 미리보기/보조 안내 줄은 골격에서 제외
    lines = []
    for line in raw.split("\n"):
        if line.startswith("[미리보기]") or line.startswith("[안내]"):
            continue
        if line.startswith("[페이지") and "원문 보조" in line:
            continue
        if line.startswith("## [PDF 페이지"):
            continue
        lines.append(line)

    locked_headings: list[str] = []
    locked_headers: list[str] = []
    out_blocks: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        trimmed = line.strip()

        if not trimmed:
            i += 1
            continue

        # 마크다운 표
        if re.fullmatch(r"\|.+\|", trimmed):
            rows: list[list[str]] = []
            while i < n and re.fullmatch(r"\|.+\|", lines[i].strip()):
                raw_line = lines[i].strip()
                if not _is_table_sep(raw_line):
                    rows.append(_split_row(raw_line))
                i += 1
            blanked, header_key = _blank_table(rows)
            if header_key:
                locked_headers.append(header_key)
            out_blocks.append(_rows_to_md(blanked))
            continue

        # 제목
        if trimmed.startswith("#") or _is_heading_line(trimmed):
            heading = _normalize_heading(trimmed)
            if heading and heading not in locked_headings:
                locked_headings.append(heading)
            # 마크다운 헤딩 레벨 유지
            if trimmed.startswith("#"):
                out_blocks.append(trimmed)
            else:
                out_blocks.append(f"## {heading}")
            i += 1
            continue

        # 일반 문단
        out_blocks.append(_blank_paragraph(trimmed))
        i += 1

    skeleton = "\n\n".join(out_blocks).strip()
    if not skeleton:
        skeleton = raw[:80000]

    return TemplateSkeleton(
        skeleton_markdown=skeleton[:80000],
        locked_headings=locked_headings[:80],
        locked_table_headers=locked_headers[:40],
        source_char_count=len(raw),
    )


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[#|*_`\-\[\]()（）]", "", s)
    return s


def fidelity_report(skeleton: TemplateSkeleton, output: str) -> tuple[float, list[str]]:
    """출력의 서식 충실도를 0~1로 평가하고 누락 항목을 반환한다."""
    missing: list[str] = []
    checks = 0
    hits = 0
    out_norm = _norm(output)

    for heading in skeleton.locked_headings:
        checks += 1
        key = _norm(heading)
        if key and key in out_norm:
            hits += 1
        else:
            # 핵심 토큰 일부라도 있으면 부분 인정
            tokens = [t for t in re.split(r"\s+", heading) if len(t) >= 2]
            if tokens and all(_norm(t) in out_norm for t in tokens[:2]):
                hits += 1
            else:
                missing.append(f"제목 누락: {heading}")

    for header in skeleton.locked_table_headers:
        checks += 1
        parts = [p.strip() for p in header.split("|") if p.strip()]
        if parts and all(_norm(p) in out_norm for p in parts[: min(3, len(parts))]):
            hits += 1
        else:
            missing.append(f"표 헤더 누락: {header}")

    if checks == 0:
        return 1.0, []
    return hits / checks, missing


def build_locked_checklist(skeleton: TemplateSkeleton) -> str:
    lines = ["## 잠긴 서식 체크리스트 (출력에 반드시 같은 순서로 포함)"]
    if skeleton.locked_headings:
        lines.append("### 제목")
        for idx, h in enumerate(skeleton.locked_headings, start=1):
            lines.append(f"{idx}. {h}")
    if skeleton.locked_table_headers:
        lines.append("### 표 헤더")
        for idx, h in enumerate(skeleton.locked_table_headers, start=1):
            lines.append(f"{idx}. {h}")
    if len(lines) == 1:
        lines.append("(원문에서 뚜렷한 제목/표 헤더를 찾지 못함 — 원문 구조를 최대한 복제)")
    return "\n".join(lines)
