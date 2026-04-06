/**
 * D3-force simulation hook for graph layout (D-01).
 *
 * - Clones input arrays before passing to D3 (Pitfall 1: D3 mutates inputs)
 * - Stores simulation in useRef, tick positions in local useState
 * - Stops simulation on unmount (Pitfall 2: no setState after unmount)
 * - Exposes simulation ref for drag reheat integration
 *
 * IMPORTANT: Tick-by-tick positions live in local useState, NOT in Zustand,
 * per anti-pattern warning in research (60fps state churn kills perf).
 */

import { useEffect, useRef, useState, type RefObject } from 'react'
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type Simulation,
} from 'd3-force'
import type { GraphNode, GraphLink } from '../types'

export interface ForceSimulationResult {
  /** Positioned nodes with x,y coordinates set by the simulation */
  positions: GraphNode[]
  /** Ref to the underlying D3 simulation for drag reheat */
  simulation: RefObject<Simulation<GraphNode, GraphLink> | null>
}

/**
 * Runs a D3-force simulation on the provided graph nodes and links.
 *
 * @param nodes - Graph nodes (NOT mutated)
 * @param links - Graph links (NOT mutated)
 * @param width - Container width for centering force
 * @param height - Container height for centering force
 */
export function useForceSimulation(
  nodes: GraphNode[],
  links: GraphLink[],
  width: number,
  height: number
): ForceSimulationResult {
  const [positions, setPositions] = useState<GraphNode[]>([])
  const simulationRef = useRef<Simulation<GraphNode, GraphLink> | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true

    // CRITICAL: Clone nodes and links to avoid mutating caller's arrays (Pitfall 1)
    const clonedNodes: GraphNode[] = nodes.map((n) => ({ ...n }))
    const clonedLinks: GraphLink[] = links.map((l) => ({ ...l }))

    const sim = forceSimulation<GraphNode>(clonedNodes)
      .force(
        'link',
        forceLink<GraphNode, GraphLink>(clonedLinks)
          .id((d) => d.id)
          .distance(80)
      )
      .force('charge', forceManyBody().strength(-200))
      .force('center', forceCenter(width / 2, height / 2))
      .force(
        'collide',
        forceCollide<GraphNode>((d) => 10 + d.confidence * 15)
      )

    simulationRef.current = sim

    // On each tick, copy positions into React state
    sim.on('tick', () => {
      if (!mountedRef.current) return
      setPositions([...clonedNodes])
    })

    // Cleanup: stop simulation on unmount (Pitfall 2)
    return () => {
      mountedRef.current = false
      sim.stop()
      simulationRef.current = null
    }
  }, [nodes, links, width, height])

  return { positions, simulation: simulationRef }
}
