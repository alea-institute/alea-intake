import { describe, it, expect } from 'vitest'
import i18n, { SUPPORTED_LANGUAGES, NAMESPACES } from './config'

describe('i18n config', () => {
  it('supports 7 LSC languages', () => {
    expect(SUPPORTED_LANGUAGES).toEqual(['en', 'es', 'zh', 'vi', 'ko', 'tl', 'ru'])
  })

  it('defines 7 namespaces', () => {
    expect(NAMESPACES).toEqual(['common', 'chat', 'admin', 'safety', 'output', 'auth', 'dashboard'])
  })

  it('initializes with fallbackLng=en', () => {
    expect(i18n.options.fallbackLng).toEqual(['en'])
  })

  it('loads only common namespace on startup', () => {
    expect(i18n.options.ns).toEqual(['common'])
  })

  it('configures http backend with locales path', () => {
    expect((i18n.options.backend as { loadPath: string }).loadPath).toBe(
      '/locales/{{lng}}/{{ns}}.json'
    )
  })
})
