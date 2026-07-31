export type AiProvider = "openai" | "anthropic" | "gemini";

export interface AiSettings {
  provider: AiProvider;
  model: string;
  apiKey: string;
}

export const PROVIDER_LABELS: Record<AiProvider, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  gemini: "Gemini",
};

/** API 키 발급 페이지 바로가기 */
export const PROVIDER_API_KEY_URLS: Record<AiProvider, string> = {
  openai: "https://platform.openai.com/api-keys",
  anthropic: "https://console.anthropic.com/settings/keys",
  gemini: "https://aistudio.google.com/apikey",
};

export const PROVIDER_MODELS: Record<AiProvider, string[]> = {
  openai: [
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-5.6",
    "gpt-5.5",
  ],
  anthropic: [
    "claude-fable-5",
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-haiku-4-5",
  ],
  gemini: [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite",
    "gemini-pro-latest",
    "gemini-flash-latest",
  ],
};

export const DEFAULT_SETTINGS: AiSettings = {
  provider: "openai",
  model: PROVIDER_MODELS.openai[0],
  apiKey: "",
};

export const STORAGE_KEY = "lesson-plan-ai-settings";
