import type {
  LibraryPrompt,
  PromptMessage,
} from '@/app/infra/entities/space-share';

/**
 * Language versions of a Space library prompt (LANG-439). The original text
 * is `messages` / `language`; `translations` holds other locales. Applying a
 * prompt uses the WebUI language with a fallback, never requiring every
 * language to exist. Mirrors langbot-space web/lib/prompt-i18n.ts.
 */
export interface PromptVersion {
  language: string;
  messages: PromptMessage[];
  original: boolean;
}

export const PROMPT_LANGUAGE_NAMES: Record<string, string> = {
  zh_Hans: '简体中文',
  zh_Hant: '繁體中文',
  en_US: 'English',
  ja_JP: '日本語',
  th_TH: 'ไทย',
  vi_VN: 'Tiếng Việt',
  es_ES: 'Español',
  ru_RU: 'Русский',
};

export function promptLanguageName(language: string) {
  return PROMPT_LANGUAGE_NAMES[language] || language;
}

export function promptVersions(
  prompt: Pick<LibraryPrompt, 'messages' | 'language' | 'translations'>,
): PromptVersion[] {
  // "und" (undetermined) when the submitter did not record a language.
  const out: PromptVersion[] = [
    {
      language: prompt.language || 'und',
      messages: prompt.messages || [],
      original: true,
    },
  ];
  for (const [language, value] of Object.entries(prompt.translations || {})) {
    if (language === prompt.language || !value?.messages?.length) continue;
    out.push({ language, messages: value.messages, original: false });
  }
  return out;
}

const family = (language: string) => language.split(/[_-]/)[0].toLowerCase();

/** Exact locale → same language family (zh_Hant ↔ zh_Hans) → English → original. */
export function pickPromptVersion(
  versions: PromptVersion[],
  uiLanguage: string,
): PromptVersion {
  const want = (uiLanguage || '').replace('-', '_');
  return (
    versions.find((v) => v.language === want) ||
    versions.find(
      (v) => v.language !== 'und' && family(v.language) === family(want),
    ) ||
    versions.find((v) => v.language === 'en_US') ||
    versions[0]
  );
}
