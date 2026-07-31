"""Markdown → 한글 HWPX(OWPML ZIP) 변환."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from xml.sax.saxutils import escape

TEMPLATE_DIR = Path(__file__).resolve().parent / "hwpx_template"

NS_DECL = (
    'xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
    'xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph" '
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" '
    'xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
    'xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history" '
    'xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page" '
    'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:opf="http://www.idpf.org/2007/opf/" '
    'xmlns:ooxmlchart="http://www.hancom.co.kr/hwpml/2016/ooxmlchart" '
    'xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar" '
    'xmlns:epub="http://www.idpf.org/2007/ops" '
    'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0"'
)

SECPR = """\
      <hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000" tabStopVal="4000" tabStopUnit="HWPUNIT" outlineShapeIDRef="1" memoShapeIDRef="0" textVerticalWidthHead="0" masterPageCnt="0">
        <hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0"/>
        <hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>
        <hp:visibility hideFirstHeader="0" hideFirstFooter="0" hideFirstMasterPage="0" border="SHOW_ALL" fill="SHOW_ALL" hideFirstPageNum="0" hideFirstEmptyLine="0" showLineNumber="0"/>
        <hp:lineNumberShape restartType="0" countBy="0" distance="0" startNumber="0"/>
        <hp:pagePr landscape="WIDELY" width="59528" height="84186" gutterType="LEFT_ONLY">
          <hp:margin header="4252" footer="4252" gutter="0" left="8504" right="8504" top="5668" bottom="4252"/>
        </hp:pagePr>
        <hp:footNotePr>
          <hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>
          <hp:noteLine length="-1" type="SOLID" width="0.12 mm" color="#000000"/>
          <hp:noteSpacing betweenNotes="283" belowLine="567" aboveLine="850"/>
          <hp:numbering type="CONTINUOUS" newNum="1"/>
          <hp:placement place="EACH_COLUMN" beneathText="0"/>
        </hp:footNotePr>
        <hp:endNotePr>
          <hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>
          <hp:noteLine length="14692344" type="SOLID" width="0.12 mm" color="#000000"/>
          <hp:noteSpacing betweenNotes="0" belowLine="567" aboveLine="850"/>
          <hp:numbering type="CONTINUOUS" newNum="1"/>
          <hp:placement place="END_OF_DOCUMENT" beneathText="0"/>
        </hp:endNotePr>
        <hp:pageBorderFill type="BOTH" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">
          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>
        </hp:pageBorderFill>
        <hp:pageBorderFill type="EVEN" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">
          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>
        </hp:pageBorderFill>
        <hp:pageBorderFill type="ODD" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">
          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>
        </hp:pageBorderFill>
      </hp:secPr>
      <hp:ctrl>
        <hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" sameSz="1" sameGap="0"/>
      </hp:ctrl>"""

PAGE_CONTENT_WIDTH = 42520
CELL_BORDER = 3
HEADER_CELL_BORDER = 4


BlockType = Literal["h1", "h2", "h3", "p", "li", "table"]


@dataclass
class Block:
    type: BlockType
    text: str = ""
    rows: list[list[str]] | None = None


def _strip_inline_md(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    return text.strip()


def _is_table_separator(line: str) -> bool:
    cells = (
        line.strip()
        .removeprefix("|")
        .removesuffix("|")
        .split("|")
    )
    cells = [c.strip() for c in cells]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c) for c in cells)


def parse_markdown_blocks(markdown: str) -> list[Block]:
    lines = markdown.replace("\r\n", "\n").split("\n")
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        trimmed = line.strip()

        if re.fullmatch(r"\|.+\|", trimmed):
            rows: list[list[str]] = []
            while i < len(lines) and re.fullmatch(r"\|.+\|", lines[i].strip()):
                raw = lines[i].strip()
                if not _is_table_separator(raw):
                    cells = [
                        _strip_inline_md(c)
                        for c in raw.removeprefix("|").removesuffix("|").split("|")
                    ]
                    rows.append(cells)
                i += 1
            if rows:
                blocks.append(Block(type="table", rows=rows))
            continue

        if line.startswith("# "):
            blocks.append(Block(type="h1", text=_strip_inline_md(line[2:])))
        elif line.startswith("## "):
            blocks.append(Block(type="h2", text=_strip_inline_md(line[3:])))
        elif line.startswith("### "):
            blocks.append(Block(type="h3", text=_strip_inline_md(line[4:])))
        elif re.match(r"^\s*[-*]\s+", line):
            blocks.append(
                Block(
                    type="li",
                    text=_strip_inline_md(re.sub(r"^\s*[-*]\s+", "", line)),
                )
            )
        elif trimmed:
            blocks.append(Block(type="p", text=_strip_inline_md(trimmed)))
        i += 1

    if not blocks:
        blocks.append(Block(type="p", text=_strip_inline_md(markdown) or " "))
    return blocks


def _xml_text(text: str) -> str:
    return escape(text or " ", {"'": "&apos;", '"': "&quot;"})


def _para(
    text: str,
    *,
    para_pr: str,
    style_id: str,
    char_pr: str,
    include_secpr: bool = False,
    para_id: int,
) -> str:
    sec = f"\n{SECPR}\n" if include_secpr else ""
    return f"""  <hp:p id="{para_id}" paraPrIDRef="{para_pr}" styleIDRef="{style_id}" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="{char_pr}">{sec}<hp:t>{_xml_text(text)}</hp:t>
    </hp:run>
  </hp:p>
"""


def _empty_first_para(para_id: int) -> str:
    return f"""  <hp:p id="{para_id}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0">
{SECPR}
    </hp:run>
    <hp:run charPrIDRef="0">
      <hp:t/>
    </hp:run>
  </hp:p>
"""


def _cell_para(text: str, para_id: int, *, bold_header: bool) -> str:
    char_pr = "6" if bold_header else "0"
    return f"""              <hp:p id="{para_id}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
                <hp:run charPrIDRef="{char_pr}">
                  <hp:t>{_xml_text(text)}</hp:t>
                </hp:run>
              </hp:p>
"""


def _make_table(rows: list[list[str]], *, start_id: int) -> tuple[str, int]:
    col_count = max((len(r) for r in rows), default=1)
    row_count = len(rows)
    col_width = max(PAGE_CONTENT_WIDTH // col_count, 2000)
    table_width = col_width * col_count
    row_height = 1400
    table_height = row_height * row_count
    pid = start_id
    table_id = pid
    pid += 1

    tr_parts: list[str] = []
    for r_idx, row in enumerate(rows):
        cells: list[str] = []
        for c_idx in range(col_count):
            cell_text = row[c_idx] if c_idx < len(row) else ""
            border = HEADER_CELL_BORDER if r_idx == 0 else CELL_BORDER
            cell_xml = f"""      <hp:tc name="" header="{'1' if r_idx == 0 else '0'}" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="{border}">
        <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">
{_cell_para(cell_text, pid, bold_header=(r_idx == 0))}        </hp:subList>
        <hp:cellAddr colAddr="{c_idx}" rowAddr="{r_idx}"/>
        <hp:cellSpan colSpan="1" rowSpan="1"/>
        <hp:cellSz width="{col_width}" height="{row_height}"/>
        <hp:cellMargin left="140" right="140" top="140" bottom="140"/>
      </hp:tc>
"""
            pid += 1
            cells.append(cell_xml)
        tr_parts.append("    <hp:tr>\n" + "".join(cells) + "    </hp:tr>\n")

    tbl = f"""  <hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0">
      <hp:tbl id="{table_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="0" repeatHeader="1" rowCnt="{row_count}" colCnt="{col_count}" cellSpacing="0" borderFillIDRef="{CELL_BORDER}" noAdjust="0">
        <hp:sz width="{table_width}" widthRelTo="ABSOLUTE" height="{table_height}" heightRelTo="ABSOLUTE" protect="0"/>
        <hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>
        <hp:outMargin left="140" right="140" top="140" bottom="140"/>
        <hp:inMargin left="141" right="141" top="141" bottom="141"/>
{''.join(tr_parts)}      </hp:tbl>
    </hp:run>
  </hp:p>
"""
    pid += 1
    return tbl, pid


_STYLE = {
    "h1": ("12", "18", "5"),
    "h2": ("13", "19", "6"),
    "h3": ("15", "21", "6"),
    "p": ("0", "0", "0"),
    "li": ("0", "0", "0"),
}


def build_section0_xml(markdown: str) -> str:
    blocks = parse_markdown_blocks(markdown)
    parts: list[str] = [f'<?xml version="1.0" encoding="UTF-8"?>\n<hs:sec {NS_DECL}>\n']
    para_id = 1

    # 첫 문단에 secPr/colPr 필수
    parts.append(_empty_first_para(para_id))
    para_id += 1

    for block in blocks:
        if block.type == "table" and block.rows:
            tbl_xml, para_id = _make_table(block.rows, start_id=para_id)
            parts.append(tbl_xml)
            continue

        text = block.text
        if block.type == "li":
            text = f"• {text}"
        para_pr, style_id, char_pr = _STYLE.get(block.type, _STYLE["p"])
        parts.append(
            _para(
                text,
                para_pr=para_pr,
                style_id=style_id,
                char_pr=char_pr,
                include_secpr=False,
                para_id=para_id,
            )
        )
        para_id += 1

    parts.append("</hs:sec>\n")
    return "".join(parts)


def _iter_template_files() -> list[tuple[str, Path]]:
    if not TEMPLATE_DIR.is_dir():
        raise FileNotFoundError(f"HWPX 템플릿이 없습니다: {TEMPLATE_DIR}")

    files: list[tuple[str, Path]] = []
    for path in TEMPLATE_DIR.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(TEMPLATE_DIR).as_posix()
        if rel in {"Contents/section0.xml", "NOTICE.txt"}:
            continue
        files.append((rel, path))
    return files


def markdown_to_hwpx_bytes(markdown: str) -> bytes:
    section_xml = build_section0_xml(markdown)
    preview = re.sub(r"\s+", " ", _strip_inline_md(markdown))[:200] or " "

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # mimetype은 반드시 첫 엔트리 + 비압축
        mime_path = TEMPLATE_DIR / "mimetype"
        zf.writestr(
            "mimetype",
            mime_path.read_bytes() if mime_path.exists() else b"application/hwp+zip",
            compress_type=zipfile.ZIP_STORED,
        )

        for arcname, path in sorted(_iter_template_files(), key=lambda x: x[0]):
            if arcname == "mimetype":
                continue
            data = path.read_bytes()
            if arcname == "Preview/PrvText.txt":
                data = preview.encode("utf-8")
            zf.writestr(arcname, data, compress_type=zipfile.ZIP_DEFLATED)

        zf.writestr(
            "Contents/section0.xml",
            section_xml.encode("utf-8"),
            compress_type=zipfile.ZIP_DEFLATED,
        )

    return buf.getvalue()
