import i18n from 'i18next'
import HttpBackend from 'i18next-http-backend'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'

export const SUPPORTED_LANGUAGES = ['en', 'es', 'zh', 'vi', 'ko', 'tl', 'ru'] as const
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number]

export const NAMESPACES = ['common', 'chat', 'admin', 'safety', 'output', 'auth', 'dashboard'] as const
export type Namespace = (typeof NAMESPACES)[number]

i18n
  .use(HttpBackend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: 'en',
    supportedLngs: SUPPORTED_LANGUAGES as unknown as string[],
    ns: ['common'],
    defaultNS: 'common',
    backend: {
      loadPath: '/locales/{{lng}}/{{ns}}.json',
      requestOptions: import.meta.env.DEV ? { cache: 'no-store' } : undefined,
    },
    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      lookupLocalStorage: 'i18nLng',
      caches: ['localStorage'],
    },
    react: { useSuspense: true },
    interpolation: { escapeValue: false },
    returnEmptyString: false,
  })

export default i18n
