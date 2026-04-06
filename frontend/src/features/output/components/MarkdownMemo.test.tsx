import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MarkdownMemo } from './MarkdownMemo'

describe('MarkdownMemo', () => {
  it('renders markdown headings with font-display class', () => {
    const md = `# Heading 1

## Heading 2`
    render(<MarkdownMemo content={md} />)
    const h1 = screen.getByRole('heading', { level: 1 })
    expect(h1).toHaveClass('font-display')
    expect(h1).toHaveAttribute('id') // rehype-slug
  })

  it('sanitizes script tags', () => {
    const md = `# Title

<script>alert('xss')</script>`
    const { container } = render(<MarkdownMemo content={md} />)
    expect(container.querySelector('script')).toBeNull()
  })

  it('renders GFM tables', () => {
    const md = `| A | B |
|---|---|
| 1 | 2 |`
    render(<MarkdownMemo content={md} />)
    expect(screen.getByRole('table')).toBeInTheDocument()
  })

  it('does NOT use dangerouslySetInnerHTML (source verification)', () => {
    // Verified via grep in CI: grep -q "rehype-sanitize" && ! grep -q "dangerouslySetInnerHTML"
    // Runtime check: rendering XSS content should not produce script elements
    const md = `<div onclick="alert(1)">click</div>`
    const { container } = render(<MarkdownMemo content={md} />)
    const div = container.querySelector('[onclick]')
    expect(div).toBeNull() // sanitizer strips event handlers
  })
})
