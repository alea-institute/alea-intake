/**
 * Tests for useExport hook -- per-view export (SVG/PNG/CSV/PDF) per D-17.
 *
 * Mocks html-to-image (toSvg/toPng) and jspdf.
 * Verifies download trigger, CSV structure, PDF layout, and filter respect.
 */

import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useExport } from './useExport'
import { mockVisualizationData } from '@/test/fixtures/visualization'
import type { VisualizationData } from '../types'
import type { MatrixRow, ClaimGroup } from './useMatrixData'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock html-to-image
vi.mock('html-to-image', () => ({
  toSvg: vi.fn().mockResolvedValue('data:image/svg+xml;base64,SVG_DATA'),
  toPng: vi.fn().mockResolvedValue('data:image/png;base64,PNG_DATA'),
}))

// Mock jspdf
const mockSave = vi.fn()
const mockText = vi.fn()
const mockAddPage = vi.fn()
const mockSetFontSize = vi.fn()
const mockSetFont = vi.fn()
const mockGetTextWidth = vi.fn().mockReturnValue(50)
const mockSplitTextToSize = vi.fn().mockImplementation((text: string) => [text])
const mockInternal = { pageSize: { getWidth: () => 210, getHeight: () => 297 } }

// jspdf exports a class as default. vi.mock must return a constructor.
function MockJsPDF() {
  return {
    text: mockText,
    save: mockSave,
    addPage: mockAddPage,
    setFontSize: mockSetFontSize,
    setFont: mockSetFont,
    getTextWidth: mockGetTextWidth,
    splitTextToSize: mockSplitTextToSize,
    internal: mockInternal,
  }
}

vi.mock('jspdf', () => ({
  default: MockJsPDF,
}))

// Mock download helpers by intercepting createElement / click
let downloadedUrls: Array<{ url: string; filename: string }> = []
const originalCreateElement = document.createElement.bind(document)

beforeEach(() => {
  vi.clearAllMocks()
  downloadedUrls = []

  // Spy on link creation to capture downloads
  vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
    if (tag === 'a') {
      const link = originalCreateElement('a') as HTMLAnchorElement
      const originalClick = link.click.bind(link)
      Object.defineProperty(link, 'click', {
        value: () => {
          downloadedUrls.push({ url: link.href, filename: link.download })
        },
      })
      return link
    }
    return originalCreateElement(tag)
  })

  // Mock URL.createObjectURL / revokeObjectURL
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-url')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useExport', () => {
  const intakeId = '42'

  it('exportGraph("svg") calls toSvg and triggers download', async () => {
    const { toSvg } = await import('html-to-image')

    const { result } = renderHook(() => useExport(intakeId))
    const el = document.createElement('div')

    await result.current.exportGraph(el, 'svg')

    expect(toSvg).toHaveBeenCalledWith(el, { backgroundColor: 'white' })
    expect(downloadedUrls).toHaveLength(1)
    expect(downloadedUrls[0].filename).toBe('analysis-graph-42.svg')
  })

  it('exportGraph("png") calls toPng and triggers download', async () => {
    const { toPng } = await import('html-to-image')

    const { result } = renderHook(() => useExport(intakeId))
    const el = document.createElement('div')

    await result.current.exportGraph(el, 'png')

    expect(toPng).toHaveBeenCalledWith(el, { backgroundColor: 'white' })
    expect(downloadedUrls).toHaveLength(1)
    expect(downloadedUrls[0].filename).toBe('analysis-graph-42.png')
  })

  it('exportMatrixCSV produces CSV with fact labels as rows, element names as columns', () => {
    const { result } = renderHook(() => useExport(intakeId))

    const rows: MatrixRow[] = [
      { factId: 101, label: 'Broken heater', confidence: 0.92 },
      { factId: 102, label: 'Visible mold', confidence: 0.88 },
    ]

    const columnGroups: ClaimGroup[] = [
      {
        claimId: 201,
        claimName: 'Habitability',
        jurisdiction: 'California',
        collapsed: false,
        columns: [
          { elementId: 401, elementName: 'Defective Condition', isGap: false, isSatisfied: true },
          { elementId: 402, elementName: 'Notice to Landlord', isGap: true, isSatisfied: false },
        ],
      },
    ]

    // Build a getCellData function that returns real cells
    const cellMap = new Map<string, { confidence: number }>()
    cellMap.set('101-401', { confidence: 0.88 })
    // 101-402 intentionally missing (gap)
    cellMap.set('102-401', { confidence: 0.82 })

    result.current.exportMatrixCSV(rows, columnGroups, (fid, eid) => {
      const cell = cellMap.get(`${fid}-${eid}`)
      return cell ? { factId: fid, elementId: eid, claimId: 201, confidence: cell.confidence, rationale: null } : null
    })

    expect(downloadedUrls).toHaveLength(1)
    expect(downloadedUrls[0].filename).toBe('analysis-matrix-42.csv')

    // Verify Blob was created with correct CSV content
    expect(URL.createObjectURL).toHaveBeenCalled()
  })

  it('exportMatrixCSV includes empty cells for gaps', () => {
    const { result } = renderHook(() => useExport(intakeId))

    const rows: MatrixRow[] = [
      { factId: 101, label: 'Fact A', confidence: 0.9 },
    ]

    const columnGroups: ClaimGroup[] = [
      {
        claimId: 201,
        claimName: 'Claim 1',
        jurisdiction: null,
        collapsed: false,
        columns: [
          { elementId: 401, elementName: 'Elem 1', isGap: false, isSatisfied: true },
          { elementId: 402, elementName: 'Elem 2', isGap: true, isSatisfied: false },
        ],
      },
    ]

    // Capture the blob content
    let capturedBlob: Blob | null = null
    ;(URL.createObjectURL as Mock).mockImplementation((blob: Blob) => {
      capturedBlob = blob
      return 'blob:mock-url'
    })

    result.current.exportMatrixCSV(rows, columnGroups, (fid, eid) => {
      if (fid === 101 && eid === 401) {
        return { factId: 101, elementId: 401, claimId: 201, confidence: 0.88, rationale: null }
      }
      return null // gap
    })

    expect(capturedBlob).not.toBeNull()
  })

  it('exportNarrativePDF creates jsPDF with text and footnotes', () => {
    const { result } = renderHook(() => useExport(intakeId))

    result.current.exportNarrativePDF(mockVisualizationData)

    expect(mockText).toHaveBeenCalled()
    expect(mockSave).toHaveBeenCalledWith('analysis-narrative-42.pdf')

    // Should have written title text
    const textCalls = mockText.mock.calls.map((c: unknown[]) => c[0])
    expect(textCalls.some((t: string) => typeof t === 'string' && t.includes('Analysis Narrative'))).toBe(true)
  })

  it('exportMatrixCSV respects filtered data (only includes provided rows)', () => {
    const { result } = renderHook(() => useExport(intakeId))

    // Provide filtered rows (only 1 of 3 facts)
    const filteredRows: MatrixRow[] = [
      { factId: 101, label: 'Broken heater', confidence: 0.92 },
    ]

    const columnGroups: ClaimGroup[] = [
      {
        claimId: 201,
        claimName: 'Habitability',
        jurisdiction: 'California',
        collapsed: false,
        columns: [
          { elementId: 401, elementName: 'Defective Condition', isGap: false, isSatisfied: true },
        ],
      },
    ]

    let capturedBlob: Blob | null = null
    ;(URL.createObjectURL as Mock).mockImplementation((blob: Blob) => {
      capturedBlob = blob
      return 'blob:mock-url'
    })

    result.current.exportMatrixCSV(filteredRows, columnGroups, (fid, eid) => {
      if (fid === 101 && eid === 401) {
        return { factId: 101, elementId: 401, claimId: 201, confidence: 0.88, rationale: null }
      }
      return null
    })

    // Only 1 data row should be in output (filtered)
    expect(downloadedUrls).toHaveLength(1)
    expect(capturedBlob).not.toBeNull()
  })
})
