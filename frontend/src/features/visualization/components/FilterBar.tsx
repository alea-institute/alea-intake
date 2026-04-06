/**
 * Shared filter controls for all visualization views (D-04/D-13).
 *
 * - Jurisdiction dropdown (populated from claims, includes "All")
 * - Claim multi-select checkboxes
 * - Confidence threshold slider (0-100, maps to 0-1)
 * - Gap-status highlight toggle
 * - ARIA: live region announces filter changes (D-14)
 */

import { useCallback, useMemo, useState } from 'react'
import { useVisualizationStore } from '../store'
import type { VisualizationData } from '../types'

interface FilterBarProps {
  data: VisualizationData | undefined
}

export function FilterBar({ data }: FilterBarProps) {
  const jurisdictionFilter = useVisualizationStore((s) => s.jurisdictionFilter)
  const claimFilter = useVisualizationStore((s) => s.claimFilter)
  const confidenceThreshold = useVisualizationStore((s) => s.confidenceThreshold)
  const showGapsOnly = useVisualizationStore((s) => s.showGapsOnly)

  const setJurisdiction = useVisualizationStore((s) => s.setJurisdiction)
  const setClaims = useVisualizationStore((s) => s.setClaims)
  const setConfidenceThreshold = useVisualizationStore((s) => s.setConfidenceThreshold)
  const toggleGapsOnly = useVisualizationStore((s) => s.toggleGapsOnly)

  const [announcement, setAnnouncement] = useState('')

  // Extract unique jurisdictions from claims
  const jurisdictions = useMemo(() => {
    if (!data) return []
    const set = new Set<string>()
    for (const claim of data.claims) {
      if (claim.jurisdiction) set.add(claim.jurisdiction)
    }
    return Array.from(set).sort()
  }, [data])

  const handleJurisdictionChange = useCallback(
    (value: string) => {
      const jurisdiction = value === 'all' ? null : value
      setJurisdiction(jurisdiction)
      setAnnouncement(`Jurisdiction filter: ${jurisdiction ?? 'All'}`)
    },
    [setJurisdiction]
  )

  const handleClaimToggle = useCallback(
    (claimId: number) => {
      const next = claimFilter.includes(claimId)
        ? claimFilter.filter((id) => id !== claimId)
        : [...claimFilter, claimId]
      setClaims(next)
      setAnnouncement(`${next.length} claims selected`)
    },
    [claimFilter, setClaims]
  )

  const handleThresholdChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = Number(e.target.value) / 100
      setConfidenceThreshold(value)
      setAnnouncement(`Confidence threshold: ${Math.round(value * 100)}%`)
    },
    [setConfidenceThreshold]
  )

  const handleGapsToggle = useCallback(() => {
    toggleGapsOnly()
    setAnnouncement(showGapsOnly ? 'Showing all items' : 'Showing gaps only')
  }, [showGapsOnly, toggleGapsOnly])

  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg bg-muted/50 p-3" role="toolbar" aria-label="Visualization filters">
      {/* ARIA live region for filter change announcements */}
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {announcement}
      </div>

      {/* Jurisdiction dropdown */}
      <div className="flex items-center gap-2">
        <label htmlFor="jurisdiction-filter" className="text-sm font-medium text-muted-foreground">
          Jurisdiction
        </label>
        <select
          id="jurisdiction-filter"
          value={jurisdictionFilter ?? 'all'}
          onChange={(e) => handleJurisdictionChange(e.target.value)}
          className="rounded-md border border-input bg-background px-2 py-1 text-sm"
        >
          <option value="all">All</option>
          {jurisdictions.map((j) => (
            <option key={j} value={j}>
              {j}
            </option>
          ))}
        </select>
      </div>

      {/* Claim multi-select checkboxes */}
      {data && data.claims.length > 0 && (
        <fieldset className="flex items-center gap-2">
          <legend className="text-sm font-medium text-muted-foreground">Claims</legend>
          {data.claims.map((claim) => (
            <label key={claim.id} className="flex items-center gap-1 text-xs">
              <input
                type="checkbox"
                checked={claimFilter.includes(claim.id)}
                onChange={() => handleClaimToggle(claim.id)}
                className="rounded border-input"
              />
              <span className="max-w-[120px] truncate" title={claim.claim_name}>
                {claim.claim_name}
              </span>
            </label>
          ))}
        </fieldset>
      )}

      {/* Confidence threshold slider */}
      <div className="flex items-center gap-2">
        <label htmlFor="confidence-threshold" className="text-sm font-medium text-muted-foreground">
          Confidence
        </label>
        <input
          type="range"
          id="confidence-threshold"
          min={0}
          max={100}
          value={Math.round(confidenceThreshold * 100)}
          onChange={handleThresholdChange}
          className="w-24"
          aria-valuenow={Math.round(confidenceThreshold * 100)}
          aria-valuemin={0}
          aria-valuemax={100}
        />
        <span className="text-xs text-muted-foreground tabular-nums">
          {Math.round(confidenceThreshold * 100)}%
        </span>
      </div>

      {/* Gap-status highlight toggle */}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={showGapsOnly}
          onChange={handleGapsToggle}
          className="rounded border-input"
        />
        <span className="font-medium text-muted-foreground">Gaps only</span>
      </label>
    </div>
  )
}
