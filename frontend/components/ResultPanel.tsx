"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { sanitizeMarkdown } from "@/lib/sanitizeMarkdown";

interface ResultPanelProps {
  markdown: string;
  loading: boolean;
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
          성취기준·단원 시수·수행평가 세부계획을 구성하는 중입니다…
        </p>
      </div>
    </div>
  );
}

export default function ResultPanel({ markdown, loading }: ResultPanelProps) {
  const cleaned = sanitizeMarkdown(markdown);

  return (
    <section className="section-panel overflow-hidden p-5 md:p-6">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-lg font-bold text-brand-900">생성 결과</h2>
        {cleaned && !loading && (
          <button
            type="button"
            onClick={() => navigator.clipboard.writeText(cleaned)}
            className="shrink-0 rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-xs font-medium text-brand-700 transition hover:bg-brand-50"
          >
            마크다운 복사
          </button>
        )}
      </div>

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
