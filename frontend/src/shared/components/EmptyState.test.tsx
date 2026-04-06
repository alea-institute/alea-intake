import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EmptyState } from './EmptyState'

describe('EmptyState', () => {
  it('renders heading, body, and action', () => {
    render(
      <EmptyState
        heading="No items"
        body="Start by adding one."
        action={<button>Add item</button>}
      />
    )
    expect(screen.getByRole('heading', { name: /no items/i })).toBeInTheDocument()
    expect(screen.getByText('Start by adding one.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /add item/i })).toBeInTheDocument()
  })

  it('renders illustration container when provided', () => {
    const { container } = render(
      <EmptyState
        illustration={<svg data-testid="illustration" />}
        heading="Empty"
      />
    )
    expect(container.querySelector('[data-testid="illustration"]')).toBeInTheDocument()
  })

  it('omits body and action when not provided', () => {
    render(<EmptyState heading="Empty" />)
    expect(screen.getByRole('heading', { name: /empty/i })).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
