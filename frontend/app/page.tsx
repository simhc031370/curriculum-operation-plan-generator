"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import AiSettingsPanel from "@/components/AiSettingsPanel";
import FileDropzone from "@/components/FileDropzone";
import ResultPanel from "@/components/ResultPanel";
import { AiSettings, DEFAULT_SETTINGS } from "@/lib/aiProviders";
import {
  CURRICULUMS,
  Curriculum,
  DEFAULT_CURRICULUM,
  DEFAULT_TOTAL_HOURS,
  GRADES_BY_LEVEL,
  SCHOOL_LEVELS,
  SchoolLevel,
} from "@/lib/schoolOptions";
import { loadAiSettings, saveAiSettings } from "@/lib/storage";

const GENERATE_API = "/api/generate";

export default function HomePage() {
  const [settings, setSettings] = useState<AiSettings>(DEFAULT_SETTINGS);
  const [hydrated, setHydrated] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [schoolLevel, setSchoolLevel] = useState<SchoolLevel>("중학교");
  const [grade, setGrade] = useState("1학년");
  const [subject, setSubject] = useState("");
  const [totalHours, setTotalHours] = useState(DEFAULT_TOTAL_HOURS);
  const [curriculum, setCurriculum] = useState<Curriculum>(DEFAULT_CURRICULUM);
  const [unitNames, setUnitNames] = useState("");
  const [performanceItems, setPerformanceItems] = useState("");
  const [loading, setLoading] = useState(false);
  const [markdown, setMarkdown] = useState("");
  const [error, setError] = useState("");

  const grades = useMemo(() => GRADES_BY_LEVEL[schoolLevel], [schoolLevel]);

  useEffect(() => {
    setSettings(loadAiSettings());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveAiSettings(settings);
  }, [settings, hydrated]);

  useEffect(() => {
    const available = GRADES_BY_LEVEL[schoolLevel];
    if (!available.includes(grade)) {
      setGrade(available[0]);
    }
  }, [schoolLevel, grade]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");

    if (!settings.apiKey.trim()) {
      setError("API Key를 입력해 주세요.");
      return;
    }
    if (!file) {
      setError("분석할 운영계획서 파일(PDF/HWP/HWPX)을 업로드해 주세요.");
      return;
    }
    if (!subject.trim()) {
      setError("과목명을 입력해 주세요.");
      return;
    }
    if (!Number.isFinite(totalHours) || totalHours < 1) {
      setError("시수(학기 단위)는 1 이상의 숫자로 입력해 주세요.");
      return;
    }
    if (!unitNames.trim()) {
      setError("해당 학기에 수업할 대단원명을 입력해 주세요.");
      return;
    }
    if (!performanceItems.trim()) {
      setError("수행평가 항목을 입력해 주세요.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("school_level", schoolLevel);
    formData.append("grade", grade);
    formData.append("subject", subject.trim());
    formData.append("total_hours", String(totalHours));
    formData.append("curriculum", curriculum);
    formData.append("unit_names", unitNames.trim());
    formData.append("performance_items", performanceItems.trim());
    formData.append("provider", settings.provider);
    formData.append("model", settings.model);
    formData.append("api_key", settings.apiKey.trim());

    setLoading(true);
    setMarkdown("");

    try {
      const response = await fetch(GENERATE_API, {
        method: "POST",
        body: formData,
      });

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        const detail =
          (data && (data.detail || data.message)) ||
          `요청 실패 (${response.status})`;
        throw new Error(
          typeof detail === "string" ? detail : JSON.stringify(detail)
        );
      }

      if (!data?.markdown) {
        throw new Error("응답에 운영계획서 내용이 없습니다.");
      }

      setMarkdown(data.markdown);
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "알 수 없는 오류가 발생했습니다.";
      const friendly =
        message === "Failed to fetch"
          ? "서버에 연결하지 못했습니다. 백엔드(포트 8000)와 프론트엔드가 실행 중인지 확인한 뒤 다시 시도해 주세요."
          : message;
      setError(friendly);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 md:py-12">
      <header className="mb-8">
        <p className="mb-2 text-sm font-semibold tracking-wide text-brand-600">
          Semester Operation Plan
        </p>
        <h1 className="text-3xl font-extrabold tracking-tight text-brand-950 md:text-4xl">
          교수학습평가 운영계획서 자동 생성
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-600 md:text-base">
          기존 운영계획서를 업로드하고 학교급·학년·과목·시수(학기 단위)·대단원·수행평가
          항목을 입력하면, AI가 문서를 분석하고 국가성취기준과 수행평가 세부계획을
          반영하여 업로드 파일과 동일한 형식으로 작성합니다.
        </p>
      </header>

      <div className="space-y-5">
        <AiSettingsPanel settings={settings} onChange={setSettings} />

        <form onSubmit={handleSubmit} className="section-panel p-5 md:p-6">
          <h2 className="mb-4 text-lg font-bold text-brand-900">입력</h2>

          <div className="space-y-5">
            <FileDropzone
              file={file}
              onFileChange={setFile}
              disabled={loading}
            />

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label htmlFor="schoolLevel" className="field-label">
                  학교급
                </label>
                <select
                  id="schoolLevel"
                  className="field-input"
                  value={schoolLevel}
                  disabled={loading}
                  onChange={(e) =>
                    setSchoolLevel(e.target.value as SchoolLevel)
                  }
                >
                  {SCHOOL_LEVELS.map((level) => (
                    <option key={level} value={level}>
                      {level}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="grade" className="field-label">
                  학년
                </label>
                <select
                  id="grade"
                  className="field-input"
                  value={grade}
                  disabled={loading}
                  onChange={(e) => setGrade(e.target.value)}
                >
                  {grades.map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="subject" className="field-label">
                  과목
                </label>
                <input
                  id="subject"
                  type="text"
                  className="field-input"
                  placeholder="예: 정보, 수학, 국어, 과학"
                  value={subject}
                  disabled={loading}
                  onChange={(e) => setSubject(e.target.value)}
                />
              </div>

              <div>
                <label htmlFor="totalHours" className="field-label">
                  시수 입력(학기 단위)
                </label>
                <input
                  id="totalHours"
                  type="number"
                  min={1}
                  max={200}
                  className="field-input"
                  placeholder="예: 17"
                  value={totalHours}
                  disabled={loading}
                  onChange={(e) => setTotalHours(Number(e.target.value))}
                />
              </div>

              <div className="md:col-span-2">
                <label htmlFor="curriculum" className="field-label">
                  국가성취기준 (교육과정)
                </label>
                <select
                  id="curriculum"
                  className="field-input"
                  value={curriculum}
                  disabled={loading}
                  onChange={(e) =>
                    setCurriculum(e.target.value as Curriculum)
                  }
                >
                  {CURRICULUMS.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
                <p className="mt-1.5 text-xs text-slate-500">
                  선택한 교육과정의 국가성취기준을 기준으로 작성합니다.
                </p>
              </div>
            </div>

            <div>
              <label htmlFor="unitNames" className="field-label">
                해당 학기 수업 대단원명
              </label>
              <textarea
                id="unitNames"
                className="field-input min-h-[120px] resize-y"
                placeholder={
                  "한 줄에 대단원명 하나씩 입력하세요.\n예:\n1. 데이터와 정보\n2. 디지털 문화와 정보윤리\n3. 문제해결과 프로그래밍"
                }
                value={unitNames}
                disabled={loading}
                onChange={(e) => setUnitNames(e.target.value)}
              />
              <p className="mt-1.5 text-xs text-slate-500">
                선택한 교육과정의 국가성취기준을 대단원에 매핑해 구체적으로
                작성합니다.
              </p>
            </div>

            <div>
              <label htmlFor="performanceItems" className="field-label">
                수행평가 항목
              </label>
              <textarea
                id="performanceItems"
                className="field-input min-h-[120px] resize-y"
                placeholder={
                  "한 줄에 항목 하나씩 입력하세요.\n예:\n1. 데이터 분석 보고서\n2. 프로그래밍 프로젝트\n3. 정보윤리 발표"
                }
                value={performanceItems}
                disabled={loading}
                onChange={(e) => setPerformanceItems(e.target.value)}
              />
              <p className="mt-1.5 text-xs text-slate-500">
                항목별 세부 평가계획을 작성하며, 2개 이상이면 총괄표와 항목별
                세부표를 함께 생성합니다.
              </p>
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-bold text-white shadow-soft transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-brand-300 md:w-auto md:min-w-[200px]"
            >
              {loading ? (
                <>
                  <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                  문서 분석·생성 중…
                </>
              ) : (
                "운영계획서 생성하기"
              )}
            </button>
          </div>
        </form>

        <ResultPanel markdown={markdown} loading={loading} />
      </div>

      <footer className="mt-10 text-center text-xs text-slate-400">
        API 키는 클라이언트에만 저장됩니다 · PDF / HWP / HWPX 분석 지원
      </footer>
    </main>
  );
}
