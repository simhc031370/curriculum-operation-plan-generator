"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  buildDownloadBaseName,
  downloadDocx,
  downloadHwpx,
  downloadHwpxBase64,
  downloadMarkdown,
} from "@/lib/downloadResult";
import { sanitizeMarkdown } from "@/lib/sanitizeMarkdown";

interface ResultPanelProps {
  markdown: string;
  loading: boolean;
  schoolLevel?: string;
  grade?: string;
  subject?: string;
  templateFidelity?: number | null;
  hwpxBase64?: string | null;
}

function LoadingState() {
  return (
    <div className="flex min-h-[220px] flex-col items-center justify-center gap-4 py-8">
      <div className="relative h-12 w-12">
        <div className="absolute inset-0 animate-spin rounded-full border-4 border-brand-100 border-t-brand-600" />
        <div className="absolute inset-2 animate-pulse rounded-full bg-brand-50" />
      </div>
      <div className="text-center">
        <p className="font-semibold text-brand-800">
          업로드 문서를 분석하고 운영계획서를 작성 중입니다
        </p>
        <p className="mt-1 text-sm text-slate-500">
          모든 항목·수행평가 세부계획을 서식에 맞게 구성하는 중입니다…
        </p>
      </div>
    </div>
  );
}

export default function ResultPanel({
  markdown,
  loading,
  schoolLevel,
  grade,
  subject,
  templateFidelity = null,
  hwpxBase64 = null,
}: ResultPanelProps) {
  const cleaned = sanitizeMarkdown(markdown);
  const [downloading, setDownloading] = useState(false);
  const baseName = buildDownloadBaseName({ schoolLevel, grade, subject });
  const fidelityLabel = hwpxBase64
    ? "원본 서식 채움"
    : typeof templateFidelity === "number"
      ? `서식 일치도 ${Math.round(templateFidelity * 100)}%`
      : null;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(cleaned);
  };

  const handleDownloadMd = () => {
    downloadMarkdown(cleaned, baseName);
  };

  const handleDownloadHwpx = async () => {
    try {
      setDownloading(true);
      if (hwpxBase64) {
        downloadHwpxBase64(hwpxBase64, baseName);
      } else {
        await downloadHwpx(cleaned, baseName);
      }
    } catch (err) {
      alert(
        err instanceof Error
          ? `한글 파일 생성 실패: ${err.message}`
          : "한글 파일 생성에 실패했습니다."
      );
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadDocx = async () => {
    try {
      setDownloading(true);
      await downloadDocx(cleaned, baseName);
    } catch (err) {
      alert(
        err instanceof Error
          ? `Word 파일 생성 실패: ${err.message}`
          : "Word 파일 생성에 실패했습니다."
      );
    } finally {
      setDownloading(false);
    }
  };

  return (
    <section className="section-panel overflow-hidden p-5 md:p-6">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-bold text-brand-900">생성 결과</h2>
          {cleaned && !loading && fidelityLabel && (
            <span className="rounded-md bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
              {fidelityLabel}
            </span>
          )}
        </div>
        {cleaned && !loading && (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleCopy}
              className="rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-xs font-medium text-brand-700 transition hover:bg-brand-50"
            >
              복사
            </button>
            <button
              type="button"
              onClick={handleDownloadMd}
              className="rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-xs font-medium text-brand-700 transition hover:bg-brand-50"
            >
              Markdown
            </button>
            <button
              type="button"
              onClick={handleDownloadDocx}
              disabled={downloading}
              className="rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-xs font-medium text-brand-700 transition hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Word(.docx)
            </button>
            <button
              type="button"
              onClick={handleDownloadHwpx}
              disabled={downloading}
              className="rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-bold text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-brand-300"
            >
              {downloading ? "파일 생성 중…" : "한글 파일(.hwpx) 다운로드"}
            </button>
          </div>
        )}
      </div>

      {cleaned && !loading && (
        <p className="mb-3 text-xs text-slate-500">
          {hwpxBase64
            ? "한글 파일은 업로드한 서식 원본에 내용을 채워 내려받습니다."
            : "한글 파일(.hwpx)은 한컴오피스 한글에서 바로 열어 편집·저장할 수 있습니다. HWPX 서식 업로드 시 원본 형식이 유지됩니다."}
        </p>
      )}

      {loading ? (
        <LoadingState />
      ) : cleaned ? (
        <div className="result-scroll max-h-[70vh] overflow-y-auto overflow-x-hidden rounded-xl border border-slate-100 bg-white px-4 py-4 md:px-5">
          <article className="prose-lesson">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ children }) => (
                  <div className="table-wrap">
                    <table>{children}</table>
                  </div>
                ),
                p: ({ children }) => <p className="break-keep">{children}</p>,
                td: ({ children }) => (
                  <td className="break-keep align-top">{children}</td>
                ),
                th: ({ children }) => (
                  <th className="break-keep align-top">{children}</th>
                ),
                br: () => <br />,
              }}
            >
              {cleaned}
            </ReactMarkdown>
          </article>
        </div>
      ) : (
        <div className="flex min-h-[180px] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/70 px-6 text-center">
          <p className="text-sm text-slate-500">
            운영계획서·교육과정·대단원·수행평가 항목을 입력한 뒤
            <br />
            생성하기를 누르면 여기에 결과가 표시됩니다.
          </p>
        </div>
      )}
    </section>
  );
}
