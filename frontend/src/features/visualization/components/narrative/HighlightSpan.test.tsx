/**
 * Tests for HighlightSpan component.
 *
 * Verifies single-claim and multi-claim highlight rendering,
 * click behavior, and accessibility attributes.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { HighlightSpan } from './HighlightSpan'
import type { TextSegment } from '../../hooks/useNarrativeData'

const baseSeg: TextSegment = {
  start: 0,
  end: 20,
  text: 'test highlighted text',
  claimIds: [201],
  factIds: [101],
  colors: ['#E69F00'],
  isAnnotated: true,
}

describe('HighlightSpan', () => {
  it('renders with semi-transparent background color from its claim color', () => {
    render(
      <HighlightSpan
        segment={baseSeg}
        isSelected={false}
        onClick={vi.fn()}
      />
    )

    const mark = screen.getByRole('mark')
    expect(mark).toBeInTheDocument()
    expect(mark.textContent).toBe('test highlighted text')

    // Should have background style with rgba (semi-transparent)
    const style = mark.getAttribute('style') ?? ''
    expect(style).toContain('background')
  })

  it('multi-claim highlight uses CSS linear-gradient with each claim color at reduced opacity (D-10)', () => {
    const multiSeg: TextSegment = {
      ...baseSeg,
      claimIds: [201, 202],
      colors: ['#E69F00', '#56B4E9'],
    }

    render(
      <HighlightSpan
        segment={multiSeg}
        isSelected={false}
        onClick={vi.fn()}
      />
    )

    const mark = screen.getByRole('mark')
    const style = mark.getAttribute('style') ?? ''
    // Should use linear-gradient for multi-claim
    expect(style).toContain('linear-gradient')
  })

  it('clicking sets store narrativeState.selectedSpanId', () => {
    const onClick = vi.fn()

    render(
      <HighlightSpan
        segment={baseSeg}
        isSelected={false}
        onClick={onClick}
      />
    )

    const mark = screen.getByRole('mark')
    fireEvent.click(mark)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('has accessible aria-label describing which claims this text supports', () => {
    render(
      <HighlightSpan
        segment={baseSeg}
        isSelected={false}
        onClick={vi.fn()}
        claimNames={['Breach of Warranty']}
      />
    )

    const mark = screen.getByRole('mark')
    const label = mark.getAttribute('aria-label') ?? ''
    expect(label).toContain('Breach of Warranty')
  })
})
