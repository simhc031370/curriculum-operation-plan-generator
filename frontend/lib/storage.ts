import {
  AiProvider,
  AiSettings,
  DEFAULT_SETTINGS,
  PROVIDER_MODELS,
  STORAGE_KEY,
} from "./aiProviders";

function isProvider(value: unknown): value is AiProvider {
  return value === "openai" || value === "anthropic" || value === "gemini";
}

export function loadAiSettings(): AiSettings {
  if (typeof window === "undefined") {
    return DEFAULT_SETTINGS;
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;

    const parsed = JSON.parse(raw) as Partial<AiSettings>;
    const provider = isProvider(parsed.provider)
      ? parsed.provider
      : DEFAULT_SETTINGS.provider;
    const models = PROVIDER_MODELS[provider];
    const model =
      typeof parsed.model === "string" && parsed.model.trim()
        ? parsed.model
        : models[0];

    return {
      provider,
      model: models.includes(model) ? model : models[0],
      apiKey: typeof parsed.apiKey === "string" ? parsed.apiKey : "",
    };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveAiSettings(settings: AiSettings): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}
