/**
 * Canvas fallback for large graphs (>=200 nodes) per D-05.
 *
 * Uses imperative 2D context rendering with requestAnimationFrame for 60fps.
 * D3-zoom attached to canvas for pan/zoom transforms.
 * Hit testing on click: distance check against all nodes.
 *
 * Note: Canvas mode loses per-node ARIA per D-05 tradeoff.
 * AccessibleTable provides the screen reader alternative.
 */

import { useEffect, useRef, useCallback } from 'react'
import { zoom as d3Zoom, zoomIdentity, type ZoomTransform } from 'd3-zoom'
import { select } from 'd3-selection'
import { useForceSimulation } from '../../hooks/useForceSimulation'
import { NODE_TYPE_COLORS } from '../../palette'
import type { GraphNode as GraphNodeType, GraphLink as GraphLinkType } from '../../types'

interface GraphCanvasProps {
  nodes: GraphNodeType[]
  links: GraphLinkType[]
  ghostedNodeIds: Set<string>
  width: number
  height: number
  onNodeClick?: (nodeId: string) => void
}

export function GraphCanvas({
  nodes,
  links,
  ghostedNodeIds,
  width,
  height,
  onNodeClick,
}: GraphCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const transformRef = useRef<ZoomTransform>(zoomIdentity)
  const animationRef = useRef<number>(0)

  const { positions, simulation } = useForceSimulation(nodes, links, width, height)
  const positionsRef = useRef(positions)
  positionsRef.current = positions

  // Drawing function
  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const t = transformRef.current
    const currentPositions = positionsRef.current

    ctx.clearRect(0, 0, width, height)
    ctx.save()
    ctx.translate(t.x, t.y)
    ctx.scale(t.k, t.k)

    // Build node lookup for link resolution
    const nodeMap = new Map<string, GraphNodeType>()
    for (const n of currentPositions) {
      nodeMap.set(n.id, n)
    }

    // Draw links
    ctx.strokeStyle = '#666'
    for (const link of links) {
      const sourceId = typeof link.source === 'string' ? link.source : link.source.id
      const targetId = typeof link.target === 'string' ? link.target : link.target.id
      const src = nodeMap.get(sourceId)
      const tgt = nodeMap.get(targetId)
      if (!src?.x || !src?.y || !tgt?.x || !tgt?.y) continue

      ctx.beginPath()
      ctx.globalAlpha = 0.3 + link.confidence * 0.7
      ctx.lineWidth = 1 + link.confidence * 2
      ctx.moveTo(src.x, src.y)
      ctx.lineTo(tgt.x, tgt.y)
      ctx.stroke()
    }

    // Draw nodes
    for (const node of currentPositions) {
      if (typeof node.x !== 'number' || typeof node.y !== 'number') continue
      const color = NODE_TYPE_COLORS[node.type]
      const alpha = ghostedNodeIds.has(node.id) ? 0.2 : 1
      ctx.globalAlpha = alpha

      const r = 6 + node.confidence * 14

      switch (node.type) {
        case 'fact': {
          ctx.beginPath()
          ctx.arc(node.x, node.y, r, 0, Math.PI * 2)
          ctx.fillStyle = color
          ctx.fill()
          break
        }
        case 'claim': {
          const w = 20 + node.confidence * 30
          const h = 14 + node.confidence * 16
          ctx.beginPath()
          roundRect(ctx, node.x - w / 2, node.y - h / 2, w, h, 4)
          ctx.fillStyle = color
          ctx.fill()
          break
        }
        case 'element': {
          const size = 8 + node.confidence * 12
          ctx.beginPath()
          ctx.moveTo(node.x, node.y - size)
          ctx.lineTo(node.x + size, node.y)
          ctx.lineTo(node.x, node.y + size)
          ctx.lineTo(node.x - size, node.y)
          ctx.closePath()
          ctx.fillStyle = color
          ctx.fill()
          break
        }
        case 'gap': {
          ctx.beginPath()
          ctx.arc(node.x, node.y, r, 0, Math.PI * 2)
          ctx.strokeStyle = color
          ctx.lineWidth = 2
          ctx.setLineDash([4, 2])
          ctx.stroke()
          ctx.setLineDash([])
          break
        }
      }
    }

    ctx.restore()
    animationRef.current = requestAnimationFrame(draw)
  }, [width, height, links, ghostedNodeIds])

  // Start render loop
  useEffect(() => {
    animationRef.current = requestAnimationFrame(draw)
    return () => {
      cancelAnimationFrame(animationRef.current)
    }
  }, [draw])

  // D3-zoom on canvas
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const zoomBehavior = d3Zoom<HTMLCanvasElement, unknown>()
      .scaleExtent([0.1, 8])
      .on('zoom', (event) => {
        transformRef.current = event.transform
      })

    select(canvas).call(zoomBehavior)

    return () => {
      select(canvas).on('.zoom', null)
    }
  }, [])

  // Hit testing on click
  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!onNodeClick) return
      const canvas = canvasRef.current
      if (!canvas) return

      const rect = canvas.getBoundingClientRect()
      const t = transformRef.current
      // Convert screen coords to graph coords
      const gx = (e.clientX - rect.left - t.x) / t.k
      const gy = (e.clientY - rect.top - t.y) / t.k

      // Find closest node within hit radius
      let closest: GraphNodeType | null = null
      let closestDist = Infinity

      for (const node of positionsRef.current) {
        if (typeof node.x !== 'number' || typeof node.y !== 'number') continue
        const dx = gx - node.x
        const dy = gy - node.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        const hitRadius = 22 // 44px / 2 for mobile hit target
        if (dist < hitRadius && dist < closestDist) {
          closest = node
          closestDist = dist
        }
      }

      if (closest) {
        onNodeClick(closest.id)
      }
    },
    [onNodeClick]
  )

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      onClick={handleClick}
      style={{ touchAction: 'none' }}
      aria-label="Force-directed graph visualization (canvas mode - use accessible table for screen reader access)"
      role="img"
    />
  )
}

// ---------------------------------------------------------------------------
// Canvas rounded-rect helper
// ---------------------------------------------------------------------------

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
) {
  ctx.moveTo(x + r, y)
  ctx.lineTo(x + w - r, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + r)
  ctx.lineTo(x + w, y + h - r)
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
  ctx.lineTo(x + r, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - r)
  ctx.lineTo(x, y + r)
  ctx.quadraticCurveTo(x, y, x + r, y)
  ctx.closePath()
}
