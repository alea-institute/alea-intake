import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import copy from '../../../public/locales/en/showcase.json'
import { ShowcaseProgress, STAGE_LABEL_KEYS, stageLabelKey } from './ShowcaseProgress'

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string, opts?: Record<string, unknown>) => {
  let value = (copy as Record<string, string>)[key] ?? key
  for (const [k, v] of Object.entries(opts ?? {})) value = value.replace(`{{${k}}}`, String(v))
  return value
} }) }))

const rawKeys = ['issue_spot', 'explore', 'research', 'fact_map', 'gap_analyze', 'question_gen', 'question', 'deadline_detect', 'converge']
afterEach(() => { vi.useRealTimers() })

describe('showcase progress', () => {
  it('maps every backend stage key to visitor copy', () => {
    for (const stage of rawKeys) {
      const label = (copy as Record<string, string>)[stageLabelKey(stage)]
      expect(label, stage).toBeTruthy()
      expect(label).not.toContain('_')
    }
    expect(Object.keys(STAGE_LABEL_KEYS).sort()).toEqual([...rawKeys].sort())
  })

  it.each(rawKeys)('never renders the raw stage key %s', stage => {
    render(<ShowcaseProgress progress={{ phase: 'analysis', stage, pct: 0, startedAt: Date.now() }} />)
    const label = (copy as Record<string, string>)[stageLabelKey(stage)]
    expect(screen.getByRole('status').textContent).toBe(`Stage 2 of 3: ${label}`)
    expect(document.body.textContent).not.toMatch(new RegExp(`\\b${stage}\\b`))
  })

  it('renders a known stage with its friendly label', () => {
    render(<ShowcaseProgress progress={{ phase: 'analysis', stage: 'fact_map', pct: 0, startedAt: Date.now() }} />)
    expect(screen.getByRole('status')).toHaveTextContent('Stage 2 of 3: Matching facts to issues')
  })

  it('falls back to the generic label for unknown or missing stages', () => {
    const { rerender } = render(<ShowcaseProgress progress={{ phase: 'analysis', stage: 'mystery_stage', startedAt: Date.now() }} />)
    expect(screen.getByRole('status')).toHaveTextContent('Stage 2 of 3: Analyzing your story')
    expect(document.body.textContent).not.toContain('mystery_stage')
    rerender(<ShowcaseProgress progress={{ phase: 'analysis', stage: null, startedAt: Date.now() }} />)
    expect(screen.getByRole('status')).toHaveTextContent('Stage 2 of 3: Analyzing your story')
  })

  it('shows the memo stage without a percentage', () => {
    render(<ShowcaseProgress progress={{ phase: 'memo', stage: 'question_gen', pct: 100, startedAt: Date.now() }} />)
    expect(screen.getByRole('status')).toHaveTextContent('Stage 3 of 3: Writing your memo')
    expect(document.body.textContent).not.toMatch(/%/)
    expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow')
  })

  it('shows real partial analysis progress, but never a fabricated or full percentage', () => {
    const { rerender } = render(<ShowcaseProgress progress={{ phase: 'analysis', stage: 'explore', pct: 40, startedAt: Date.now() }} />)
    expect(screen.getByText('40% complete')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '40')
    rerender(<ShowcaseProgress progress={{ phase: 'analysis', stage: 'question_gen', pct: 100, startedAt: Date.now() }} />)
    expect(document.body.textContent).not.toMatch(/%/)
    rerender(<ShowcaseProgress progress={{ phase: 'analysis', stage: 'issue_spot', pct: 0, startedAt: Date.now() }} />)
    expect(document.body.textContent).not.toMatch(/%/)
  })

  it('advances the elapsed clock every second outside the live region', () => {
    vi.useFakeTimers()
    render(<ShowcaseProgress progress={{ phase: 'analysis', stage: 'issue_spot', startedAt: Date.now() }} />)
    const elapsed = screen.getByTestId('showcase-elapsed')
    expect(elapsed).toHaveTextContent('· 0 s')
    act(() => { vi.advanceTimersByTime(1000) })
    expect(elapsed).toHaveTextContent('· 1 s')
    act(() => { vi.advanceTimersByTime(44000) })
    expect(elapsed).toHaveTextContent('· 45 s')
    expect(screen.getByRole('status')).not.toContainElement(elapsed)
    expect(screen.getByRole('status')).toHaveTextContent('Stage 2 of 3: Spotting legal issues')
  })
})
