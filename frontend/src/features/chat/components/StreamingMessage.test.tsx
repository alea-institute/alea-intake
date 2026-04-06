import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { StreamingMessage } from './StreamingMessage'

const base = {
  id: 'm1',
  sessionId: 's1',
  sender: 'system' as const,
  modality: 'text' as const,
  content: 'Hel',
  timestamp: 't',
}

describe('StreamingMessage', () => {
  it('shows stop button while streaming', () => {
    renderWithProviders(
      <StreamingMessage message={{ ...base, status: 'streaming' }} onStop={() => {}} />,
    )
    expect(screen.getByRole('button', { name: /stop/i })).toBeInTheDocument()
  })

  it('hides stop button when done', () => {
    renderWithProviders(<StreamingMessage message={{ ...base, status: 'done' }} />)
    expect(screen.queryByRole('button', { name: /stop/i })).not.toBeInTheDocument()
  })

  it('calls onStop when clicked', async () => {
    const onStop = vi.fn()
    renderWithProviders(
      <StreamingMessage message={{ ...base, status: 'streaming' }} onStop={onStop} />,
    )
    await userEvent.click(screen.getByRole('button', { name: /stop/i }))
    expect(onStop).toHaveBeenCalled()
  })

  it('renders content text', () => {
    renderWithProviders(
      <StreamingMessage message={{ ...base, status: 'streaming' }} />,
    )
    expect(screen.getByText('Hel')).toBeInTheDocument()
  })

  it('has aria-live polite region', () => {
    renderWithProviders(
      <StreamingMessage message={{ ...base, status: 'streaming' }} />,
    )
    expect(screen.getByRole('article')).toHaveAttribute('aria-live', 'polite')
  })
})
