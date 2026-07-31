"""문서 파싱 모듈.

지원 형식: PDF, HWP, HWPX
표·문단 구조를 최대한 마크다운으로 보존해 AI가 서식을 따라 채울 수 있게 한다.
"""

from __future__ import annotations

import re
import struct
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET

import olefile
import pdfplumber
from PyPDF2 import PdfReader

SUPPORTED_EXTENSIONS = {".pdf", ".hwp", ".hwpx"}


def extract_text_from_file(file_path: str) -> str:
    """업로드된 임시 파일에서 구조 보존 텍스트를 추출한다."""
    path = Path(file_path)
    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"지원하지 않는 파일 형식입니다: {extension or '(확장자 없음)'}. "
            f"현재 지원: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if extension == ".pdf":
        return _extract_from_pdf(path)
    if extension == ".hwp":
        return _extract_from_hwp(path)
    if extension == ".hwpx":
        return _extract_from_hwpx(path)

    raise ValueError(f"파서가 구현되지 않은 형식입니다: {extension}")


def _local(tag: str) -> str:
    return tag.split("}")[-1].lower() if tag else ""


def _normalize_ws(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def _extract_from_pdf(path: Path) -> str:
    structured = _extract_pdf_structured(path)
    if structured.strip():
        return structured

    text = _extract_with_pdfplumber(path)
    if text.strip():
        return text

    text = _extract_with_pypdf2(path)
    if text.strip():
        return text

    raise ValueError(
        "PDF에서 텍스트를 추출하지 못했습니다. "
        "스캔본(이미지 PDF)이거나 보호된 파일일 수 있습니다."
    )


def _rows_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    normalized: list[list[str]] = []
    for row in rows:
        cells = [(c or "").replace("\n", " ").strip() for c in row]
        while len(cells) < width:
            cells.append("")
        normalized.append(cells[:width])

    header = normalized[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in normalized[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _extract_pdf_structured(path: Path) -> str:
    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            page_chunks: list[str] = []
            tables = page.extract_tables() or []
            table_mds: list[str] = []
            for table in tables:
                rows = [
                    [(cell or "").strip() for cell in row]
                    for row in table
                    if row and any((cell or "").strip() for cell in row)
                ]
                md = _rows_to_markdown(rows)
                if md:
                    table_mds.append(md)

            text = (page.extract_text() or "").strip()
            if table_mds:
                page_chunks.extend(table_mds)
                if text:
                    page_chunks.append(f"[페이지 {idx} 원문 보조]\n{text}")
            elif text:
                page_chunks.append(text)

            if page_chunks:
                parts.append(f"## [PDF 페이지 {idx}]\n" + "\n\n".join(page_chunks))

    return _normalize_ws("\n\n".join(parts))


def _extract_with_pdfplumber(path: Path) -> str:
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(page_text)
    return "\n\n".join(pages)


def _extract_with_pypdf2(path: Path) -> str:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages.append(page_text)
    return "\n\n".join(pages)


# ---------------------------------------------------------------------------
# HWP
# ---------------------------------------------------------------------------


def _extract_from_hwp(path: Path) -> str:
    """HWP 5.x OLE 컨테이너에서 BodyText 섹션 텍스트를 추출한다."""
    if not olefile.isOleFile(str(path)):
        raise ValueError(
            "올바른 HWP 파일이 아닙니다. "
            "한글 2010 이후 HWP 또는 HWPX 파일을 업로드해 주세요."
        )

    texts: list[str] = []
    with olefile.OleFileIO(str(path)) as ole:
        section_names = [
            name
            for name in ole.listdir()
            if len(name) >= 2
            and name[0].lower() == "bodytext"
            and name[1].lower().startswith("section")
        ]
        section_names.sort(key=lambda n: n[1])

        if not section_names:
            raise ValueError("HWP 본문(BodyText)을 찾지 못했습니다.")

        for name in section_names:
            raw = ole.openstream(name).read()
            texts.append(_decode_hwp_section(raw))

    combined = "\n\n".join(t for t in texts if t.strip()).strip()
    if not combined:
        raise ValueError(
            "HWP에서 텍스트를 추출하지 못했습니다. "
            "암호가 설정되었거나 이미지 위주 문서일 수 있습니다. "
            "가능하면 한글에서 HWPX로 저장해 다시 업로드해 주세요."
        )
    # 표 구조는 HWP 바이너리에서 복원이 어려워 안내를 덧붙인다.
    notice = (
        "[안내] HWP(바이너리)에서는 표 칸 경계를 완전히 복원하기 어렵습니다. "
        "가능하면 동일 문서를 HWPX로 저장해 업로드하면 서식(표·문단) 충실도가 높아집니다.\n\n"
    )
    return notice + _normalize_ws(combined)


def _decode_hwp_section(data: bytes) -> str:
    """압축된 HWP 섹션에서 문단 단위로 텍스트를 최대한 복원한다."""
    payload = data
    try:
        payload = zlib.decompress(data, -15)
    except zlib.error:
        try:
            payload = zlib.decompress(data)
        except zlib.error:
            payload = data

    # HWP 레코드: header(4bytes) + data
    # tagID = header & 0x3FF, level = (header >> 10) & 0x3FF, size = (header >> 20) & 0xFFF
    # tag 67 = HWPTAG_PARA_TEXT
    paragraphs: list[str] = []
    i = 0
    n = len(payload)
    while i + 4 <= n:
        header = struct.unpack_from("<I", payload, i)[0]
        tag_id = header & 0x3FF
        size = (header >> 20) & 0xFFF
        i += 4
        if size == 0xFFF:
            if i + 4 > n:
                break
            size = struct.unpack_from("<I", payload, i)[0]
            i += 4
        if i + size > n:
            break
        record = payload[i : i + size]
        i += size

        if tag_id != 67:  # HWPTAG_PARA_TEXT
            continue

        chars: list[str] = []
        j = 0
        while j + 2 <= len(record):
            code = struct.unpack_from("<H", record, j)[0]
            j += 2
            # 컨트롤 문자 영역은 건너뛴다 (확장 컨트롤은 추가 바이트 소모)
            if code in {0x0001, 0x0002, 0x0003, 0x0004, 0x0005, 0x0006, 0x0007,
                        0x0008, 0x0009, 0x000A, 0x000B, 0x000C, 0x000D, 0x0010,
                        0x0011, 0x0012, 0x0013, 0x0014, 0x0015, 0x0016, 0x0017,
                        0x0018, 0x0019, 0x001A, 0x001B, 0x001C, 0x001D, 0x001E,
                        0x001F}:
                # inline control: often followed by 14 more uint16 (total 16 units) for extended
                if code in {0x0001, 0x0002, 0x0003, 0x000B, 0x000C, 0x000E, 0x000F,
                            0x0011, 0x0012, 0x0013, 0x0015, 0x0016, 0x0017}:
                    # extended control size roughly 14 extra code units after the marker
                    j += 14 * 2
                if code in {0x000A, 0x000D}:
                    chars.append("\n")
                continue
            if code == 0:
                continue
            if (
                0x20 <= code <= 0x7E
                or 0xAC00 <= code <= 0xD7A3
                or 0x3131 <= code <= 0x318E
                or 0x1100 <= code <= 0x11FF
                or code in {0x201C, 0x201D, 0x2018, 0x2019, 0x3001, 0x3002,
                            0xFF0C, 0xFF1A, 0xFF1B, 0xFF01, 0xFF1F}
            ):
                chars.append(chr(code))

        para = "".join(chars).strip()
        if para:
            paragraphs.append(para)

    if paragraphs:
        return "\n".join(paragraphs)

    # 레코드 파싱 실패 시 기존 스캔 폴백
    chars = []
    for k in range(0, len(payload) - 1, 2):
        code = struct.unpack_from("<H", payload, k)[0]
        if code == 0:
            continue
        if (
            0x20 <= code <= 0x7E
            or 0xAC00 <= code <= 0xD7A3
            or code in {0x0A, 0x0D, 0x09}
            or 0x3131 <= code <= 0x318E
        ):
            chars.append(chr(code))
    text = "".join(chars)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# HWPX
# ---------------------------------------------------------------------------


def _extract_from_hwpx(path: Path) -> str:
    """HWPX(ZIP+XML)에서 문단·표를 마크다운 골격으로 추출한다."""
    if not zipfile.is_zipfile(path):
        raise ValueError("올바른 HWPX 파일이 아닙니다.")

    parts: list[str] = []
    with zipfile.ZipFile(path, "r") as zf:
        # 미리보기 텍스트가 있으면 보조로 포함
        for preview_name in ("Preview/PrvText.txt", "preview/PrvText.txt"):
            if preview_name in zf.namelist():
                preview = zf.read(preview_name).decode("utf-8", errors="ignore").strip()
                if preview and preview not in {".", ".."}:
                    parts.append(f"[미리보기]\n{preview}")
                break

        section_files = sorted(
            name
            for name in zf.namelist()
            if re.search(r"(^|/)section\d+\.xml$", name, re.I)
        )
        if not section_files:
            section_files = sorted(
                name
                for name in zf.namelist()
                if "/section" in name.lower() and name.lower().endswith(".xml")
            )

        for name in section_files:
            try:
                xml_bytes = zf.read(name)
            except KeyError:
                continue
            section_md = _hwpx_section_to_markdown(xml_bytes)
            if section_md.strip():
                parts.append(section_md)

    combined = _normalize_ws("\n\n".join(parts))
    if not combined:
        raise ValueError("HWPX에서 텍스트를 추출하지 못했습니다.")
    return combined


def _hwpx_section_to_markdown(xml_bytes: bytes) -> str:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        decoded = xml_bytes.decode("utf-8", errors="ignore")
        return _normalize_ws(re.sub(r"<[^>]+>", "\n", decoded))

    parent_map = {c: p for p in root.iter() for c in p}

    def inside_table(el: ET.Element) -> bool:
        cur = parent_map.get(el)
        while cur is not None:
            if _local(cur.tag) in {"tbl", "tc"}:
                return True
            cur = parent_map.get(cur)
        return False

    blocks: list[str] = []
    seen_tables: set[int] = set()

    for elem in root.iter():
        tag = _local(elem.tag)
        if tag == "tbl":
            tid = id(elem)
            if tid in seen_tables:
                continue
            seen_tables.add(tid)
            table_md = _hwpx_table_to_markdown(elem)
            if table_md:
                blocks.append(table_md)
            continue

        if tag != "p" or inside_table(elem):
            continue

        # run 안에 표가 중첩된 경우가 많음 → 표 텍스트는 표 변환에서만 처리
        has_nested_tbl = any(
            _local(x.tag) == "tbl" for x in elem.iter() if x is not elem
        )
        text = _hwpx_para_text(elem, skip_table=True) if has_nested_tbl else _hwpx_para_text(
            elem, skip_table=False
        )
        if text:
            blocks.append(_format_heading_line(text))

    deduped: list[str] = []
    prev = None
    for block in blocks:
        if block == prev:
            continue
        deduped.append(block)
        prev = block
    return "\n\n".join(deduped)


def _hwpx_para_text(para: ET.Element, *, skip_table: bool) -> str:
    chunks: list[str] = []

    def walk(node: ET.Element) -> None:
        if skip_table and _local(node.tag) == "tbl":
            return
        if _local(node.tag) == "t" and node.text:
            chunks.append(node.text)
        for child in list(node):
            walk(child)
            if child.tail and child.tail.strip() and _local(node.tag) != "tbl":
                # tail은 자식 뒤 텍스트
                if not (skip_table and _local(child.tag) == "tbl"):
                    chunks.append(child.tail)

    walk(para)
    return _normalize_ws("".join(chunks))


def _hwpx_table_to_markdown(tbl: ET.Element) -> str:
    rows: list[list[str]] = []
    for tr in tbl:
        if _local(tr.tag) != "tr":
            continue
        row: list[str] = []
        for tc in tr:
            if _local(tc.tag) != "tc":
                continue
            cell_parts: list[str] = []
            for p in tc.iter():
                if _local(p.tag) != "p":
                    continue
                # 중첩 표의 p는 제외
                text = _hwpx_cell_para_text(p)
                if text:
                    cell_parts.append(text)
            cell = " / ".join(cell_parts).replace("|", "/")
            row.append(cell)
        if row:
            rows.append(row)
    return _rows_to_markdown(rows)


def _hwpx_cell_para_text(para: ET.Element) -> str:
    chunks: list[str] = []
    for elem in para.iter():
        if _local(elem.tag) == "t" and elem.text:
            chunks.append(elem.text)
    return _normalize_ws("".join(chunks))


def _format_heading_line(text: str) -> str:
    """짧은 제목형 문단은 마크다운 헤딩으로 승격해 골격이 보이게 한다."""
    compact = text.strip()
    if not compact:
        return ""
    # 이미 번호 체계·절 제목처럼 보이는 경우
    if re.match(
        r"^(제?\s*\d+\s*[장절항]|[IVXLC]+\.|[0-9]+(\.[0-9]+)*\.?|[가-하]\.|[①-⑮]|\d+\))",
        compact,
    ):
        if len(compact) <= 40:
            return f"## {compact}"
        return f"### {compact}"
    if len(compact) <= 28 and not compact.endswith(("다.", "요.", "음.", "함.")):
        # 짧은 제목 후보
        if any(key in compact for key in ("계획", "평가", "기준", "시수", "단원", "목표", "방침", "운영")):
            return f"## {compact}"
    return compact
