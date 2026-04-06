import { describe, it, expect, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { IntakeVirtualList } from './IntakeVirtualList'

describe('IntakeVirtualList', () => {
  beforeEach(() => {
    // Mock getBoundingClientRect for the scroll container so virtualizer can compute visible rows
    Element.prototype.getBoundingClientRect = function () {
      if (this.getAttribute('role') === 'list') {
        return { top: 0, left: 0, bottom: 600, right: 800, width: 800, height: 600, x: 0, y: 0, toJSON: () => {} } as DOMRect
      }
      return { top: 0, left: 0, bottom: 0, right: 0, width: 0, height: 0, x: 0, y: 0, toJSON: () => {} } as DOMRect
    }
    // Mock offsetHeight for the scroll container
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
      configurable: true,
      get() { return this.getAttribute('role') === 'list' ? 600 : 0 },
    })
  })

  it('uses useFlushSync: false (verified via source)', async () => {
    // This is a static assertion -- the source file must contain useFlushSync: false
    const fs = await import('fs')
    const path = await import('path')
    const src = fs.readFileSync(
      path.resolve(__dirname, './IntakeVirtualList.tsx'),
      'utf-8'
    )
    expect(src).toContain('useFlushSync: false')
  })

  it('renders virtual list container', () => {
    const intakes = Array.from({ length: 200 }, (_, i) => ({
      id: `i${i}`,
      matterId: `M-${i}`,
      consumerName: `User ${i}`,
      status: 'new' as const,
      lastActivity: '2026-04-01',
      completeness: 0,
    }))
    const { container } = render(
      <MemoryRouter>
        <IntakeVirtualList intakes={intakes} />
      </MemoryRouter>
    )
    // Virtual list should create a container with role="list"
    const listEl = container.querySelector('[role="list"]')
    expect(listEl).toBeInTheDocument()
    // The total height div should exist and be larger than the container
    const innerDiv = listEl?.firstElementChild as HTMLElement
    expect(innerDiv).toBeTruthy()
    const totalHeight = parseInt(innerDiv.style.height, 10)
    expect(totalHeight).toBeGreaterThan(600) // 200 rows * 72px each = 14400px
  })
})
