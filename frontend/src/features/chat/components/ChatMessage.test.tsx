import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import { ChatMessage } from './ChatMessage'

const base = {
  id: 'm1',
  sessionId: 's1',
  content: 'Hello',
  timestamp: '2026-04-05T10:00:00Z',
  status: 'sent' as const,
}

describe('ChatMessage', () => {
  it('renders consumer messages with avatar on left', () => {
    renderWithProviders(
      <ChatMessage message={{ ...base, sender: 'consumer', modality: 'text' }} />,
    )
    expect(screen.getByText('Hello')).toBeInTheDocument()
    expect(screen.getByText('You')).toBeInTheDocument()
  })

  it('renders system messages with AI badge', () => {
    renderWithProviders(
      <ChatMessage message={{ ...base, sender: 'system', modality: 'text' }} />,
    )
    expect(screen.getByText('AI')).toBeInTheDocument()
  })

  it('shows modality sr-only label', () => {
    renderWithProviders(
      <ChatMessage message={{ ...base, sender: 'consumer', modality: 'voice' }} />,
    )
    expect(screen.getByText(/voice/i)).toBeInTheDocument()
  })

  it('applies opacity to pending messages', () => {
    const { container } = renderWithProviders(
      <ChatMessage
        message={{ ...base, sender: 'consumer', modality: 'text', status: 'pending' }}
      />,
    )
    expect(container.querySelector('.opacity-50')).toBeInTheDocument()
  })

  it('has aria-label on article element', () => {
    renderWithProviders(
      <ChatMessage message={{ ...base, sender: 'consumer', modality: 'text' }} />,
    )
    expect(screen.getByRole('article')).toHaveAttribute(
      'aria-label',
      expect.stringContaining('you'),
    )
  })
})
