/**
 * 생성 결과 다운로드 유틸 (Markdown / Word DOCX)
 * DOCX는 한글(한컴오피스)에서도 바로 열 수 있습니다.
 */

import {
  Document,
  HeadingLevel,
  Packer,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
  BorderStyle,
} from "docx";

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function downloadMarkdown(markdown: string, baseName: string) {
  const blob = new Blob(["\uFEFF" + markdown], {
    type: "text/markdown;charset=utf-8",
  });
  triggerDownload(blob, `${baseName}.md`);
}

type Block =
  | { type: "h1" | "h2" | "h3" | "p" | "li"; text: string }
  | { type: "table"; rows: string[][] };

function isTableSeparator(line: string): boolean {
  const cells = line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());
  return cells.length > 0 && cells.every((c) => /^:?-{3,}:?$/.test(c));
}

function parseMarkdownBlocks(markdown: string): Block[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (/^\|.+\|$/.test(trimmed)) {
      const rows: string[][] = [];
      while (i < lines.length && /^\|.+\|$/.test(lines[i].trim())) {
        const raw = lines[i].trim();
        if (!isTableSeparator(raw)) {
          const cells = raw
            .replace(/^\|/, "")
            .replace(/\|$/, "")
            .split("|")
            .map((c) => c.trim());
          rows.push(cells);
        }
        i += 1;
      }
      if (rows.length) blocks.push({ type: "table", rows });
      continue;
    }

    if (line.startsWith("# ")) {
      blocks.push({ type: "h1", text: line.slice(2).trim() });
    } else if (line.startsWith("## ")) {
      blocks.push({ type: "h2", text: line.slice(3).trim() });
    } else if (line.startsWith("### ")) {
      blocks.push({ type: "h3", text: line.slice(4).trim() });
    } else if (/^\s*[-*]\s+/.test(line)) {
      blocks.push({ type: "li", text: line.replace(/^\s*[-*]\s+/, "").trim() });
    } else if (trimmed) {
      blocks.push({ type: "p", text: trimmed });
    }
    i += 1;
  }

  return blocks;
}

function stripInlineMd(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[(.*?)\]\((.*?)\)/g, "$1");
}

const thinBorder = {
  top: { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1" },
  bottom: { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1" },
  left: { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1" },
  right: { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1" },
};

export async function downloadDocx(markdown: string, baseName: string) {
  const blocks = parseMarkdownBlocks(markdown);
  const children: (Paragraph | Table)[] = [];

  for (const block of blocks) {
    if (block.type === "table") {
      const colCount = Math.max(...block.rows.map((r) => r.length), 1);
      const rows = block.rows.map(
        (row, rowIndex) =>
          new TableRow({
            children: Array.from({ length: colCount }, (_, idx) => {
              const cell = row[idx] ?? "";
              return new TableCell({
                borders: thinBorder,
                width: {
                  size: Math.floor(9000 / colCount),
                  type: WidthType.DXA,
                },
                children: [
                  new Paragraph({
                    children: [
                      new TextRun({
                        text: stripInlineMd(cell),
                        bold: rowIndex === 0,
                        size: 18,
                        font: "Malgun Gothic",
                      }),
                    ],
                  }),
                ],
              });
            }),
          })
      );
      children.push(
        new Table({
          width: { size: 9000, type: WidthType.DXA },
          rows,
        })
      );
      children.push(new Paragraph({ text: "" }));
      continue;
    }

    const text = stripInlineMd(block.text);
    if (block.type === "h1") {
      children.push(
        new Paragraph({
          text,
          heading: HeadingLevel.HEADING_1,
          spacing: { before: 200, after: 120 },
        })
      );
    } else if (block.type === "h2") {
      children.push(
        new Paragraph({
          text,
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 180, after: 100 },
        })
      );
    } else if (block.type === "h3") {
      children.push(
        new Paragraph({
          text,
          heading: HeadingLevel.HEADING_3,
          spacing: { before: 140, after: 80 },
        })
      );
    } else if (block.type === "li") {
      children.push(
        new Paragraph({
          children: [
            new TextRun({
              text: `• ${text}`,
              size: 20,
              font: "Malgun Gothic",
            }),
          ],
          spacing: { after: 60 },
        })
      );
    } else {
      children.push(
        new Paragraph({
          children: [
            new TextRun({ text, size: 20, font: "Malgun Gothic" }),
          ],
          spacing: { after: 80 },
        })
      );
    }
  }

  const doc = new Document({
    sections: [
      {
        properties: {
          page: {
            margin: { top: 720, bottom: 720, left: 720, right: 720 },
          },
        },
        children:
          children.length > 0
            ? children
            : [
                new Paragraph({
                  children: [
                    new TextRun({
                      text: stripInlineMd(markdown),
                      font: "Malgun Gothic",
                      size: 20,
                    }),
                  ],
                }),
              ],
      },
    ],
  });

  const blob = await Packer.toBlob(doc);
  triggerDownload(blob, `${baseName}.docx`);
}

export function buildDownloadBaseName(meta: {
  schoolLevel?: string;
  grade?: string;
  subject?: string;
}): string {
  const parts = [
    meta.schoolLevel,
    meta.grade,
    meta.subject,
    "교수학습평가운영계획서",
  ].filter(Boolean);
  const raw = parts.join("_") || "교수학습평가운영계획서";
  return raw.replace(/[\\/:*?"<>|]/g, "").replace(/\s+/g, "");
}
