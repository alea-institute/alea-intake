/**
 * useExport hook -- per-view export logic for SVG/PNG/CSV/PDF per D-17.
 *
 * Returns three export functions that respect current filter state:
 * - exportGraph: SVG or PNG via html-to-image
 * - exportMatrixCSV: CSV with fact labels as rows, element names as columns
 * - exportMatrixPNG: PNG via html-to-image on matrix container
 * - exportNarrativePDF: jsPDF document with text and annotation footnotes
 *
 * Note: Narrative PDF is MVP plain-text-with-footnotes per research recommendation.
 * Server-side WeasyPrint could provide higher fidelity highlight reproduction.
 */

import { useCallback } from 'react'
import jsPDF from 'jspdf'
import type { VisualizationData, MatrixCell } from '../types'
import type { MatrixRow, ClaimGroup } from './useMatrixData'

// ---------------------------------------------------------------------------
// Download helpers
// ---------------------------------------------------------------------------

function downloadDataUrl(dataUrl: string, filename: string): void {
  const a = document.createElement('a')
  a.href = dataUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ---------------------------------------------------------------------------
// CSV helpers
// ---------------------------------------------------------------------------

/** Quote a CSV cell value: wrap in quotes and escape internal quotes */
function csvCell(value: string): string {
  const escaped = value.replace(/"/g, '""')
  return `"${escaped}"`
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useExport(intakeId: string) {
  /**
   * Export the graph view as SVG or PNG.
   * Uses html-to-image for DOM-to-image conversion.
   * For Canvas mode, use canvas.toDataURL directly.
   */
  const exportGraph = useCallback(
    async (element: HTMLElement, format: 'svg' | 'png') => {
      // Wait for React to flush state before capture (Pitfall 6)
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))

      const { toSvg, toPng } = await import('html-to-image')

      const dataUrl =
        format === 'svg'
          ? await toSvg(element, { backgroundColor: 'white' })
          : await toPng(element, { backgroundColor: 'white' })

      downloadDataUrl(dataUrl, `analysis-graph-${intakeId}.${format}`)
    },
    [intakeId]
  )

  /**
   * Export the matrix view as CSV.
   * Rows = facts, columns = elements grouped by claim.
   * Empty cells for gaps (no mapping).
   * Accepts pre-filtered data so exports respect current filter state.
   */
  const exportMatrixCSV = useCallback(
    (
      rows: MatrixRow[],
      columnGroups: ClaimGroup[],
      getCellData: (factId: number, elementId: number) => MatrixCell | null
    ) => {
      // Flatten visible columns (skip collapsed groups)
      const flatColumns = columnGroups.flatMap((g) =>
        g.collapsed ? [] : g.columns
      )

      // Header row: "Fact", then element names
      const header = [
        csvCell('Fact'),
        ...flatColumns.map((col) => csvCell(col.elementName)),
      ].join(',')

      // Data rows
      const dataRows = rows.map((row) => {
        const cells = flatColumns.map((col) => {
          const cell = getCellData(row.factId, col.elementId)
          return cell ? csvCell(String(Math.round(cell.confidence * 100))) : ''
        })
        return [csvCell(row.label), ...cells].join(',')
      })

      const csvContent = [header, ...dataRows].join('\n')
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' })
      downloadBlob(blob, `analysis-matrix-${intakeId}.csv`)
    },
    [intakeId]
  )

  /**
   * Export the matrix view as PNG (visual screenshot).
   */
  const exportMatrixPNG = useCallback(
    async (element: HTMLElement) => {
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))

      const { toPng } = await import('html-to-image')
      const dataUrl = await toPng(element, { backgroundColor: 'white' })
      downloadDataUrl(dataUrl, `analysis-matrix-${intakeId}.png`)
    },
    [intakeId]
  )

  /**
   * Export the narrative view as annotated PDF.
   * MVP: plain text with footnote markers and a footnotes section.
   * Each message renders with sender header, text, and superscript claim references.
   */
  const exportNarrativePDF = useCallback(
    (data: VisualizationData) => {
      const doc = new jsPDF()

      const pageWidth = doc.internal.pageSize.getWidth()
      const pageHeight = doc.internal.pageSize.getHeight()
      const margin = 20
      const maxWidth = pageWidth - margin * 2
      let y = margin

      // Build claim name lookup
      const claimNames = new Map<number, string>()
      for (const claim of data.claims) {
        claimNames.set(claim.id, claim.claim_name)
      }

      // Build fact -> claim mappings for footnote references
      const factClaimMap = new Map<number, Set<number>>()
      for (const mapping of data.mappings) {
        if (!factClaimMap.has(mapping.fact_id)) {
          factClaimMap.set(mapping.fact_id, new Set())
        }
        factClaimMap.get(mapping.fact_id)!.add(mapping.claim_id)
      }

      // Collect footnotes as we go
      const footnotes: Array<{ index: number; claimNames: string[]; confidence: number }> = []
      let footnoteCounter = 0

      // Title
      doc.setFontSize(16)
      doc.setFont('helvetica', 'bold')
      doc.text('Analysis Narrative', margin, y)
      y += 10

      doc.setFontSize(12)

      // Render each message
      for (const msg of data.messages) {
        // Check page break
        if (y > pageHeight - margin - 20) {
          doc.addPage()
          y = margin
        }

        // Sender label (bold)
        doc.setFont('helvetica', 'bold')
        const senderLabel =
          msg.sender_type === 'consumer'
            ? 'Consumer'
            : msg.sender_type === 'professional'
              ? 'Professional'
              : msg.sender_type
        doc.text(senderLabel, margin, y)
        y += 7

        // Message text (normal)
        doc.setFont('helvetica', 'normal')

        // Find facts referenced in this message
        const messageFacts = data.facts.filter((f) =>
          f.source_spans.some((s) => s.message_id === msg.id)
        )

        // Build text with footnote markers
        let text = msg.content
        const messageFootnotes: string[] = []

        for (const fact of messageFacts) {
          const relatedClaimIds = factClaimMap.get(fact.id)
          if (relatedClaimIds && relatedClaimIds.size > 0) {
            footnoteCounter++
            const names = Array.from(relatedClaimIds).map(
              (cid) => claimNames.get(cid) ?? `Claim ${cid}`
            )
            const avgConfidence =
              data.mappings
                .filter((m) => m.fact_id === fact.id && relatedClaimIds.has(m.claim_id))
                .reduce((sum, m) => sum + m.confidence, 0) /
              data.mappings.filter(
                (m) => m.fact_id === fact.id && relatedClaimIds.has(m.claim_id)
              ).length

            footnotes.push({
              index: footnoteCounter,
              claimNames: names,
              confidence: avgConfidence,
            })
            messageFootnotes.push(`[${footnoteCounter}]`)
          }
        }

        // Append footnote markers to text
        const annotatedText = messageFootnotes.length > 0
          ? `${text} ${messageFootnotes.join(' ')}`
          : text

        // Split text to fit page width
        const lines: string[] = doc.splitTextToSize(annotatedText, maxWidth)
        for (const line of lines) {
          if (y > pageHeight - margin) {
            doc.addPage()
            y = margin
          }
          doc.text(line, margin, y)
          y += 6
        }

        y += 4 // spacing between messages
      }

      // Footnotes section
      if (footnotes.length > 0) {
        if (y > pageHeight - margin - 30) {
          doc.addPage()
          y = margin
        }

        y += 6
        doc.setFont('helvetica', 'bold')
        doc.setFontSize(11)
        doc.text('Footnotes', margin, y)
        y += 7

        doc.setFont('helvetica', 'normal')
        doc.setFontSize(10)

        for (const fn of footnotes) {
          if (y > pageHeight - margin) {
            doc.addPage()
            y = margin
          }
          const fnText = `[${fn.index}] ${fn.claimNames.join(', ')} (confidence: ${Math.round(fn.confidence * 100)}%)`
          doc.text(fnText, margin, y)
          y += 5
        }
      }

      doc.save(`analysis-narrative-${intakeId}.pdf`)
    },
    [intakeId]
  )

  return {
    exportGraph,
    exportMatrixCSV,
    exportMatrixPNG,
    exportNarrativePDF,
  }
}
