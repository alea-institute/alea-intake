/**
 * SVG graph container with D3-force layout, zoom/pan, and node interaction (D-01, D-03).
 *
 * - Uses useForceSimulation for physics-based node positioning
 * - D3-zoom for pan/zoom (touch support for mobile D-16)
 * - Renders GraphLink[] then GraphNode[] (links behind nodes)
 * - Node click sets selectedNodeId in store (triggers DetailPanel)
 * - Keyboard: Enter/Space on focused node triggers click
 */

import { useEffect, useRef, useCallback, useMemo } from 'react'
import { zoom as d3Zoom, type ZoomBehavior } from 'd3-zoom'
import { select } from 'd3-selection'
import { useForceSimulation } from '../../hooks/useForceSimulation'
import { GraphNode } from './GraphNode'
import { GraphLink } from './GraphLink'
import type { GraphNode as GraphNodeType, GraphLink as GraphLinkType } from '../../types'

interface GraphViewProps {
  nodes: GraphNodeType[]
  links: GraphLinkType[]
  ghostedNodeIds: Set<string>
  width: number
  height: number
  selectedNodeId?: string | null
  onNodeClick?: (nodeId: string) => void
}

export function GraphView({
  nodes,
  links,
  ghostedNodeIds,
  width,
  height,
  selectedNodeId,
  onNodeClick,
}: GraphViewProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const gRef = useRef<SVGGElement>(null)
  const zoomRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null)

  const { positions } = useForceSimulation(nodes, links, width, height)

  // Build a lookup from node ID -> positioned node
  const positionMap = useMemo(() => {
    const map = new Map<string, GraphNodeType & { x: number; y: number }>()
    for (const p of positions) {
      if (typeof p.x === 'number' && typeof p.y === 'number') {
        map.set(p.id, p as GraphNodeType & { x: number; y: number })
      }
    }
    return map
  }, [positions])

  // Resolve links to positioned source/target
  const resolvedLinks = useMemo(() => {
    return links
      .map((link, i) => {
        const sourceId = typeof link.source === 'string' ? link.source : link.source.id
        const targetId = typeof link.target === 'string' ? link.target : link.target.id
        const source = positionMap.get(sourceId)
        const target = positionMap.get(targetId)
        if (!source || !target) return null
        return { source, target, confidence: link.confidence, index: i }
      })
      .filter(Boolean) as Array<{
        source: GraphNodeType & { x: number; y: number }
        target: GraphNodeType & { x: number; y: number }
        confidence: number
        index: number
      }>
  }, [links, positionMap])

  // D3-zoom setup
  useEffect(() => {
    if (!svgRef.current || !gRef.current) return

    const svgEl = svgRef.current
    const gEl = gRef.current

    const zoomBehavior = d3Zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 8])
      .on('zoom', (event) => {
        gEl.setAttribute('transform', event.transform.toString())
      })

    select(svgEl).call(zoomBehavior)
    // Enable touch gestures for mobile (D-16)
    select(svgEl).call(zoomBehavior).on('dblclick.zoom', null)

    zoomRef.current = zoomBehavior

    return () => {
      select(svgEl).on('.zoom', null)
    }
  }, [])

  const handleNodeClick = useCallback(
    (nodeId: string) => {
      onNodeClick?.(nodeId)
    },
    [onNodeClick]
  )

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Force-directed graph visualization of facts, claims, and elements"
      style={{ touchAction: 'none' }}
    >
      <g ref={gRef}>
        {/* Links rendered first (behind nodes) */}
        {resolvedLinks.map((rl) => (
          <GraphLink
            key={`link-${rl.index}`}
            source={rl.source}
            target={rl.target}
            confidence={rl.confidence}
            index={rl.index}
          />
        ))}

        {/* Nodes rendered on top */}
        {Array.from(positionMap.values()).map((posNode) => (
          <GraphNode
            key={posNode.id}
            node={posNode}
            ghosted={ghostedNodeIds.has(posNode.id)}
            selected={selectedNodeId === posNode.id}
            onClick={handleNodeClick}
          />
        ))}
      </g>
    </svg>
  )
}
