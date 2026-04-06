/**
 * Accessible data table alternative for all three visualization views (D-14).
 *
 * - Graph mode: table with Node Name, Type, Confidence, Connected Nodes columns
 * - Matrix mode: standard HTML table with fact rows x element columns
 * - Narrative mode: text with footnote-style annotations
 *
 * Proper semantic HTML: thead, tbody, th with scope attributes.
 * Auto-detected by screen readers via aria-hidden on visualization.
 */

import type { VisualizationData, ViewType } from '../types'

interface AccessibleTableProps {
  mode: ViewType
  data: VisualizationData
}

export function AccessibleTable({ mode, data }: AccessibleTableProps) {
  if (mode === 'graph') return <GraphTable data={data} />
  if (mode === 'matrix') return <MatrixTable data={data} />
  return <NarrativeText data={data} />
}

// ---------------------------------------------------------------------------
// Graph mode: node list with connections
// ---------------------------------------------------------------------------

interface NodeRow {
  name: string
  type: string
  confidence: number
  connectedTo: string[]
}

function GraphTable({ data }: { data: VisualizationData }) {
  const rows: NodeRow[] = []

  // Build a mapping lookup for connections
  const mappingsByFact = new Map<number, number[]>()
  const mappingsByClaim = new Map<number, number[]>()
  for (const m of data.mappings) {
    if (!mappingsByFact.has(m.fact_id)) mappingsByFact.set(m.fact_id, [])
    mappingsByFact.get(m.fact_id)!.push(m.claim_id)
    if (!mappingsByClaim.has(m.claim_id)) mappingsByClaim.set(m.claim_id, [])
    mappingsByClaim.get(m.claim_id)!.push(m.fact_id)
  }

  // Claim name lookup
  const claimNames = new Map<number, string>()
  for (const c of data.claims) {
    claimNames.set(c.id, c.claim_name)
  }

  // Fact label lookup
  const factLabels = new Map<number, string>()
  for (const f of data.facts) {
    factLabels.set(f.id, f.assertion_text.slice(0, 60))
  }

  // Facts
  for (const fact of data.facts) {
    const connectedClaimIds = mappingsByFact.get(fact.id) ?? []
    const connected = [...new Set(connectedClaimIds)].map(
      (cid) => claimNames.get(cid) ?? `Claim ${cid}`
    )
    rows.push({
      name: fact.assertion_text,
      type: 'Fact',
      confidence: fact.confidence,
      connectedTo: connected,
    })
  }

  // Claims
  for (const claim of data.claims) {
    const connectedFactIds = mappingsByClaim.get(claim.id) ?? []
    const connected = [...new Set(connectedFactIds)].map(
      (fid) => factLabels.get(fid) ?? `Fact ${fid}`
    )
    rows.push({
      name: claim.claim_name,
      type: 'Claim',
      confidence: claim.confidence,
      connectedTo: connected,
    })
  }

  // Elements
  for (const claim of data.claims) {
    for (const elem of claim.elements) {
      rows.push({
        name: elem.element_name,
        type: 'Element',
        confidence: elem.satisfaction_confidence ?? 0,
        connectedTo: [claim.claim_name],
      })
    }
  }

  // Gaps
  for (const gap of data.gaps) {
    const parentClaim = gap.claim_id ? claimNames.get(gap.claim_id) : null
    rows.push({
      name: gap.description,
      type: 'Gap',
      confidence: gap.priority / 5,
      connectedTo: parentClaim ? [parentClaim] : [],
    })
  }

  return (
    <table role="table" className="w-full border-collapse text-sm">
      <thead>
        <tr>
          <th scope="col" className="border-b px-3 py-2 text-left font-medium">
            Node
          </th>
          <th scope="col" className="border-b px-3 py-2 text-left font-medium">
            Type
          </th>
          <th scope="col" className="border-b px-3 py-2 text-left font-medium">
            Confidence
          </th>
          <th scope="col" className="border-b px-3 py-2 text-left font-medium">
            Connected To
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className="border-b last:border-b-0">
            <td className="px-3 py-2">{row.name}</td>
            <td className="px-3 py-2">{row.type}</td>
            <td className="px-3 py-2">{Math.round(row.confidence * 100)}%</td>
            <td className="px-3 py-2">{row.connectedTo.join(', ') || 'None'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// ---------------------------------------------------------------------------
// Matrix mode: fact x element table
// ---------------------------------------------------------------------------

function MatrixTable({ data }: { data: VisualizationData }) {
  // Flatten all elements with their claim context
  const allElements: Array<{ id: number; name: string; claimName: string }> = []
  for (const claim of data.claims) {
    for (const elem of claim.elements) {
      allElements.push({
        id: elem.id,
        name: elem.element_name,
        claimName: claim.claim_name,
      })
    }
  }

  // Build mapping lookup: (factId, elementId) -> confidence
  const mappingLookup = new Map<string, number>()
  for (const m of data.mappings) {
    if (m.element_id != null) {
      mappingLookup.set(`${m.fact_id}-${m.element_id}`, m.confidence)
    }
  }

  return (
    <table role="table" className="w-full border-collapse text-sm">
      <thead>
        <tr>
          <th scope="col" className="border-b px-3 py-2 text-left font-medium">
            Fact
          </th>
          {allElements.map((elem) => (
            <th
              key={elem.id}
              scope="col"
              className="border-b px-3 py-2 text-center font-medium"
              title={`${elem.claimName}: ${elem.name}`}
            >
              {elem.name}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.facts.map((fact) => (
          <tr key={fact.id} className="border-b last:border-b-0">
            <td className="px-3 py-2">{fact.assertion_text.slice(0, 50)}</td>
            {allElements.map((elem) => {
              const conf = mappingLookup.get(`${fact.id}-${elem.id}`)
              return (
                <td key={elem.id} className="px-3 py-2 text-center">
                  {conf != null ? `${Math.round(conf * 100)}%` : '-'}
                </td>
              )
            })}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// ---------------------------------------------------------------------------
// Narrative mode: annotated text with footnotes
// ---------------------------------------------------------------------------

function NarrativeText({ data }: { data: VisualizationData }) {
  // Claim name lookup
  const claimNames = new Map<number, string>()
  for (const c of data.claims) {
    claimNames.set(c.id, c.claim_name)
  }

  return (
    <div className="space-y-4 text-sm" role="document">
      {data.facts.map((fact) => {
        // Find claims this fact maps to
        const relatedClaims = data.mappings
          .filter((m) => m.fact_id === fact.id)
          .map((m) => claimNames.get(m.claim_id) ?? `Claim ${m.claim_id}`)

        const uniqueClaims = [...new Set(relatedClaims)]

        return (
          <p key={fact.id}>
            {fact.assertion_text}
            {uniqueClaims.length > 0 && (
              <sup className="ml-0.5 text-xs text-muted-foreground">
                [{uniqueClaims.join(', ')}]
              </sup>
            )}
          </p>
        )
      })}
    </div>
  )
}
