import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { TranscriptReview } from './TranscriptReview'

describe('TranscriptReview', () => {
  it('renders editable textarea with transcript', () => {
    renderWithProviders(<TranscriptReview transcript="Hello world" audioUrl="blob:x" onApprove={() => {}} onReRecord={() => {}} />)
    expect(screen.getByRole('textbox')).toHaveValue('Hello world')
  })

  it('renders audio element with src', () => {
    renderWithProviders(<TranscriptReview transcript="hi" audioUrl="blob:audio" onApprove={() => {}} onReRecord={() => {}} />)
    const audio = document.querySelector('audio')
    expect(audio).toBeTruthy()
    expect(audio?.getAttribute('src')).toBe('blob:audio')
  })

  it('highlights low-confidence words', () => {
    const { container } = renderWithProviders(<TranscriptReview transcript="hello uncertain world" audioUrl="blob:x" confidence={[0.9, 0.3, 0.9]} onApprove={() => {}} onReRecord={() => {}} />)
    const hint = container.querySelector('#low-conf-hint')
    expect(hint).toBeTruthy()
    expect(hint!.textContent).toContain('uncertain')
  })

  it('calls onApprove with edited text', async () => {
    const onApprove = vi.fn()
    renderWithProviders(<TranscriptReview transcript="hi" audioUrl="blob:x" onApprove={onApprove} onReRecord={() => {}} />)
    const textarea = screen.getByRole('textbox')
    await userEvent.clear(textarea)
    await userEvent.type(textarea, 'edited')
    await userEvent.click(screen.getByRole('button', { name: /approve/i }))
    expect(onApprove).toHaveBeenCalledWith('edited')
  })

  it('calls onReRecord', async () => {
    const onReRecord = vi.fn()
    renderWithProviders(<TranscriptReview transcript="hi" audioUrl="blob:x" onApprove={() => {}} onReRecord={onReRecord} />)
    await userEvent.click(screen.getByRole('button', { name: /re-record/i }))
    expect(onReRecord).toHaveBeenCalled()
  })
})
