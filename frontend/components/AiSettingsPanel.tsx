"use client";

import {
  AiProvider,
  AiSettings,
  PROVIDER_API_KEY_URLS,
  PROVIDER_LABELS,
  PROVIDER_MODELS,
} from "@/lib/aiProviders";

interface AiSettingsPanelProps {
  settings: AiSettings;
  onChange: (next: AiSettings) => void;
}

export default function AiSettingsPanel({
  settings,
  onChange,
}: AiSettingsPanelProps) {
  const models = PROVIDER_MODELS[settings.provider];
  const currentKeyUrl = PROVIDER_API_KEY_URLS[settings.provider];

  const handleProviderChange = (provider: AiProvider) => {
    onChange({
      ...settings,
      provider,
      model: PROVIDER_MODELS[provider][0],
    });
  };

  return (
    <section className="section-panel p-5 md:p-6">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-brand-900">AI 설정</h2>
          <p className="mt-1 text-sm text-slate-500">
            API 키는 브라우저 localStorage에만 저장되며 서버에 영구 보관되지
            않습니다.
          </p>
        </div>
        <span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
          BYOK
        </span>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {(Object.keys(PROVIDER_API_KEY_URLS) as AiProvider[]).map((key) => (
          <a
            key={key}
            href={PROVIDER_API_KEY_URLS[key]}
            target="_blank"
            rel="noopener noreferrer"
            className={[
              "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition",
              settings.provider === key
                ? "border-brand-500 bg-brand-50 text-brand-800"
                : "border-slate-200 bg-white text-slate-600 hover:border-brand-300 hover:bg-brand-50/60 hover:text-brand-700",
            ].join(" ")}
          >
            {PROVIDER_LABELS[key]} API 키 받기
            <span aria-hidden className="text-[10px] opacity-70">
              ↗
            </span>
          </a>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div>
          <label htmlFor="provider" className="field-label">
            AI 공급사
          </label>
          <select
            id="provider"
            className="field-input"
            value={settings.provider}
            onChange={(e) =>
              handleProviderChange(e.target.value as AiProvider)
            }
          >
            {(Object.keys(PROVIDER_LABELS) as AiProvider[]).map((key) => (
              <option key={key} value={key}>
                {PROVIDER_LABELS[key]}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="model" className="field-label">
            모델
          </label>
          <select
            id="model"
            className="field-input"
            value={settings.model}
            onChange={(e) =>
              onChange({ ...settings, model: e.target.value })
            }
          >
            {models.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <label htmlFor="apiKey" className="field-label mb-0">
              API Key
            </label>
            <a
              href={currentKeyUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-medium text-brand-600 hover:text-brand-800 hover:underline"
            >
              {PROVIDER_LABELS[settings.provider]} 키 발급 바로가기
            </a>
          </div>
          <input
            id="apiKey"
            type="password"
            autoComplete="off"
            className="field-input"
            placeholder={`${PROVIDER_LABELS[settings.provider]} API Key`}
            value={settings.apiKey}
            onChange={(e) =>
              onChange({ ...settings, apiKey: e.target.value })
            }
          />
        </div>
      </div>
    </section>
  );
}
