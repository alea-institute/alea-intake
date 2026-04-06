/**
 * Tests for AccessibleTable -- screen-reader-friendly data table alternative (D-14).
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AccessibleTable } from './AccessibleTable'
import { mockVisualizationData } from '@/test/fixtures/visualization'

describe('AccessibleTable', () => {
  it('renders HTML table with Node, Type, Confidence, Connected To columns', () => {
    render(
      <AccessibleTable mode="graph" data={mockVisualizationData} />
    )

    expect(screen.getByText('Node')).toBeTruthy()
    expect(screen.getByText('Type')).toBeTruthy()
    expect(screen.getByText('Confidence')).toBeTruthy()
    expect(screen.getByText('Connected To')).toBeTruthy()
  })

  it('has proper table semantics (thead, tbody, th scope)', () => {
    const { container } = render(
      <AccessibleTable mode="graph" data={mockVisualizationData} />
    )

    expect(container.querySelector('thead')).toBeTruthy()
    expect(container.querySelector('tbody')).toBeTruthy()

    const thElements = container.querySelectorAll('th')
    expect(thElements.length).toBeGreaterThan(0)

    // All header th elements should have scope="col"
    thElements.forEach((th) => {
      expect(th.getAttribute('scope')).toBe('col')
    })
  })

  it('renders rows for all node types', () => {
    const { container } = render(
      <AccessibleTable mode="graph" data={mockVisualizationData} />
    )

    const rows = container.querySelectorAll('tbody tr')
    // facts + claims + elements + gaps
    const expectedRows =
      mockVisualizationData.facts.length +
      mockVisualizationData.claims.length +
      mockVisualizationData.claims.reduce((s, c) => s + c.elements.length, 0) +
      mockVisualizationData.gaps.length

    expect(rows.length).toBe(expectedRows)
  })
})
