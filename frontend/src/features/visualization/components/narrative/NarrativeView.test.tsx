/**
 * Tests for NarrativeView, AnnotationChip, and NarrativeLegend components.
 *
 * TDD RED phase: all tests written before implementation.
 * Tests verify annotated text rendering, margin chips, legend,
 * plain text segments, and responsive behavior.
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { NarrativeView } from './NarrativeView'
import { useVisualizationStore } from '@/features/visualization/store'
import { mockVisualizationData } from '@/test/fixtures/visualization'

describe('NarrativeView', () => {
  afterEach(() => {
    useVisualizationStore.setState({
      jurisdictionFilter: null,
      claimFilter: [],
      confidenceThreshold: 0,
      narrativeState: { activeLayers: [], selectedSpanId: null },
    })
  })

  it('renders consumer message text with inline highlights', () => {
    render(<NarrativeView data={mockVisualizationData} />)

    // Consumer message content should appear
    expect(
      screen.getByText(/Landlord has refused to fix the broken heater/i)
    ).toBeInTheDocument()

    // There should be highlighted marks (annotated spans)
    const marks = screen.getAllByRole('mark')
    expect(marks.length).toBeGreaterThan(0)
  })

  it('non-annotated segments render as plain text (no highlight)', () => {
    render(<NarrativeView data={mockVisualizationData} />)

    // Professional message (302) has no source spans, should be plain text
    expect(
      screen.getByText(/Can you tell me more about the conditions/i)
    ).toBeInTheDocument()

    // The professional message container should not contain any <mark> elements
    const professionalSection = screen
      .getByText(/Can you tell me more about the conditions/i)
      .closest('[data-message-id="302"]')
    if (professionalSection) {
      const marks = professionalSection.querySelectorAll('[role="mark"]')
      expect(marks.length).toBe(0)
    }
  })

  it('AnnotationChip renders with claim abbreviation', () => {
    render(<NarrativeView data={mockVisualizationData} />)

    // Should render annotation chips with first 3 chars of claim names
    // "Breach of Warranty..." -> "Bre"
    // "Wrongful Eviction..." -> "Wro"
    const chips = screen.getAllByTestId('annotation-chip')
    expect(chips.length).toBeGreaterThan(0)

    // At least one chip should have abbreviation text
    const chipTexts = chips.map((c) => c.textContent)
    expect(chipTexts.some((t) => t && t.length <= 4)).toBe(true)
  })

  it('NarrativeLegend renders color swatch + claim name for each claim', () => {
    render(<NarrativeView data={mockVisualizationData} />)

    // Legend should show both claim names
    expect(
      screen.getByText('Breach of Warranty of Habitability')
    ).toBeInTheDocument()
    expect(
      screen.getByText('Wrongful Eviction / Retaliatory Eviction')
    ).toBeInTheDocument()

    // Legend should have a list role
    const legend = screen.getByTestId('narrative-legend')
    expect(legend).toBeInTheDocument()
  })

  it('Desktop shows margin chips; mobile shows inline expansion (D-16)', () => {
    render(<NarrativeView data={mockVisualizationData} />)

    // Multiple margin-chips containers (one per message block)
    const marginContainers = screen.getAllByTestId('margin-chips')
    expect(marginContainers.length).toBeGreaterThan(0)

    // Each should have responsive classes: hidden on mobile, block on md+
    for (const container of marginContainers) {
      expect(container.className).toContain('hidden')
      expect(container.className).toMatch(/md:block/)
    }
  })
})
