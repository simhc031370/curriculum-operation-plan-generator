"use client";

import { useCallback, useRef, useState } from "react";

interface FileDropzoneProps {
  file: File | null;
  onFileChange: (file: File | null) => void;
  disabled?: boolean;
}

const ACCEPT = ".pdf,.hwp,.hwpx,application/pdf";

function isAllowedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return (
    name.endsWith(".pdf") ||
    name.endsWith(".hwp") ||
    name.endsWith(".hwpx") ||
    file.type === "application/pdf"
  );
}

export default function FileDropzone({
  file,
  onFileChange,
  disabled = false,
}: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const pickFile = useCallback(
    (candidate: File | undefined | null) => {
      if (!candidate) return;
      if (!isAllowedFile(candidate)) {
        alert("PDF, HWP, HWPX 파일만 업로드할 수 있습니다.");
        return;
      }
      onFileChange(candidate);
    },
    [onFileChange]
  );

  return (
    <div>
      <label className="field-label">참고 운영계획서 업로드</label>
      <div
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (disabled) return;
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onClick={() => {
          if (!disabled) inputRef.current?.click();
        }}
        onDragEnter={(e) => {
          e.preventDefault();
          e.stopPropagation();
          if (!disabled) setDragging(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setDragging(false);
          if (disabled) return;
          pickFile(e.dataTransfer.files?.[0]);
        }}
        className={[
          "flex min-h-[168px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-4 py-8 text-center transition",
          dragging
            ? "border-brand-500 bg-brand-50"
            : "border-brand-200 bg-brand-50/40 hover:border-brand-400 hover:bg-brand-50/70",
          disabled ? "cursor-not-allowed opacity-60" : "",
        ].join(" ")}
      >
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-white text-brand-600 shadow-sm ring-1 ring-brand-100">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            className="h-6 w-6"
            aria-hidden
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 16V4m0 0 4 4m-4-4-4 4M4 16.5V18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1.5"
            />
          </svg>
        </div>

        {file ? (
          <>
            <p className="text-sm font-semibold text-brand-800">{file.name}</p>
            <p className="mt-1 text-xs text-slate-500">
              {(file.size / 1024 / 1024).toFixed(2)} MB · 클릭하여 다른 파일 선택
            </p>
            <button
              type="button"
              className="mt-3 text-xs font-medium text-rose-600 hover:underline"
              onClick={(e) => {
                e.stopPropagation();
                onFileChange(null);
                if (inputRef.current) inputRef.current.value = "";
              }}
            >
              파일 제거
            </button>
          </>
        ) : (
          <>
            <p className="text-sm font-semibold text-brand-800">
              파일을 드래그 앤 드롭하거나 클릭하여 업로드
            </p>
            <p className="mt-1 text-xs text-slate-500">
              기존 운영계획서 · PDF / HWP / HWPX
            </p>
          </>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        disabled={disabled}
        onChange={(e) => pickFile(e.target.files?.[0])}
      />
    </div>
  );
}
