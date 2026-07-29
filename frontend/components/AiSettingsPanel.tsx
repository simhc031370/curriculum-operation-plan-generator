"use client";

import {
  AiProvider,
  AiSettings,
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
          <label htmlFor="apiKey" className="field-label">
            API Key
          </label>
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
