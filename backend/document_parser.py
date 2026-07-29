"""문서 파싱 모듈.

지원 형식: PDF, HWP, HWPX
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
    """업로드된 임시 파일에서 텍스트를 추출한다."""
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


def _extract_from_pdf(path: Path) -> str:
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
            "암호가 설정되었거나 이미지 위주 문서일 수 있습니다."
        )
    return combined


def _decode_hwp_section(data: bytes) -> str:
    """압축된 HWP 섹션 바이트에서 유니코드 문자만 최대한 추출한다."""
    payload = data
    # 많은 HWP 본문 섹션은 zlib로 압축되어 있음
    try:
        payload = zlib.decompress(data, -15)
    except zlib.error:
        try:
            payload = zlib.decompress(data)
        except zlib.error:
            payload = data

    chars: list[str] = []
    # UTF-16LE 코드 유닛을 훑으며 출력 가능한 한글/ASCII를 모은다
    for i in range(0, len(payload) - 1, 2):
        code = struct.unpack_from("<H", payload, i)[0]
        if code == 0:
            continue
        if (
            0x20 <= code <= 0x7E
            or 0xAC00 <= code <= 0xD7A3
            or code in {0x0A, 0x0D, 0x09}
            or 0x3131 <= code <= 0x318E
            or 0x1100 <= code <= 0x11FF
        ):
            chars.append(chr(code))

    text = "".join(chars)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_from_hwpx(path: Path) -> str:
    """HWPX(ZIP+XML)에서 섹션 XML 텍스트를 추출한다."""
    if not zipfile.is_zipfile(path):
        raise ValueError("올바른 HWPX 파일이 아닙니다.")

    texts: list[str] = []
    with zipfile.ZipFile(path, "r") as zf:
        section_files = sorted(
            name
            for name in zf.namelist()
            if "/section" in name.lower() and name.lower().endswith(".xml")
        )
        if not section_files:
            section_files = sorted(
                name for name in zf.namelist() if name.lower().endswith(".xml")
            )

        for name in section_files:
            try:
                xml_bytes = zf.read(name)
            except KeyError:
                continue
            texts.append(_extract_text_from_xml_bytes(xml_bytes))

    combined = "\n\n".join(t for t in texts if t.strip()).strip()
    if not combined:
        raise ValueError("HWPX에서 텍스트를 추출하지 못했습니다.")
    return combined


def _extract_text_from_xml_bytes(xml_bytes: bytes) -> str:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        # 깨진 XML이면 태그 제거 폴백
        decoded = xml_bytes.decode("utf-8", errors="ignore")
        return re.sub(r"<[^>]+>", " ", decoded)

    chunks: list[str] = []
    for elem in root.iter():
        tag = elem.tag.split("}")[-1].lower()
        if tag in {"t", "text", "char"} and elem.text:
            chunks.append(elem.text)
        elif elem.text and tag not in {"script", "style"}:
            # 기타 노드의 짧은 텍스트도 보조적으로 포함
            stripped = elem.text.strip()
            if stripped and len(stripped) < 500:
                chunks.append(stripped)
        if elem.tail and elem.tail.strip():
            chunks.append(elem.tail.strip())

    text = " ".join(chunks)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
