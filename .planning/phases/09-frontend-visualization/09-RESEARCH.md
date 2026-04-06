# Phase 9: Frontend Visualization - Research

**Researched:** 2026-04-03
**Domain:** D3-force graph, virtual matrix, narrative annotation -- React visualization components
**Confidence:** HIGH

## Summary

This phase builds three specialized fact-mapping visualization views on top of the existing React + Zustand + React Query + shadcn frontend. The force-directed graph uses D3-force for simulation with React rendering SVG DOM (Canvas fallback at 200+ nodes). The fact-element matrix uses @tanstack/react-virtual (already installed) for bidirectional virtualization. The narrative-anchored view highlights source text spans with overlapping claim annotations. All three views share a Zustand filter context, tab-based view switching, accessible data table fallbacks, and per-view export.

A critical finding: the current `/api/v1/analysis/{intake_id}/results` endpoint returns claims, gaps, and questions but does NOT return fact-claim mappings (`FactClaimMapping` records), extracted facts (`ExtractedFact` records), or source spans (`FactSourceSpan` records). The visualizations require all of these. The API must be extended to serve a consolidated visualization data payload before the frontend views can function.

**Primary recommendation:** Use modular D3 packages (d3-force, d3-selection, d3-zoom, d3-drag) instead of the full d3 bundle to control bundle size. Build a single `useForceSimulation` hook that outputs positioned nodes/links, then render via React SVG (or imperative Canvas above threshold). Extend the analysis results API to include facts, mappings, and source spans in a single request.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** D3-force + thin React wrapper (SVG). Force simulation via D3, React handles DOM and event binding. Most flexible, best performance for typical legal analysis graphs (100-500 nodes).
- **D-02:** Node encoding: shape + color by type (Facts=circles, Claims=rounded rectangles, Elements=diamonds), size proportional to confidence score. Low-confidence nodes smaller/lighter. Gaps highlighted with dashed borders. Colors from theme categorical palette.
- **D-03:** Click node opens a slide-out detail panel showing: node type info (fact text, claim description, element requirements), connected edges with confidence, source spans, authorities. Panel stays open while exploring. Professional can annotate from panel.
- **D-04:** Filter bar: toggle node types (facts/claims/elements), jurisdiction selector, confidence threshold slider, gap-status highlight. Filtered-out nodes fade to ghosted (stay visible for spatial context).
- **D-05:** SVG for <200 nodes (crisp, accessible, per-node events). Auto-switch to HTML5 Canvas for >200 nodes (60fps at 1000+). Canvas mode loses per-node ARIA. Threshold configurable.
- **D-06:** Facts as rows, elements grouped by claim as columns. Column headers are collapsible per claim. Gap columns highlighted with warning indicator.
- **D-07:** Cells: 5-level color scale (strong/good/partial/weak/none) matching theme + subtle numeric confidence scores visible in each cell. Hover shows: confidence score, mapping rationale, source span. Click opens same detail panel as graph view. Empty cells (gaps) have diagonal stripe pattern.
- **D-08:** Virtual scrolling (@tanstack/react-virtual) for both rows and columns + sticky claim headers and fact labels. Handles 500+ facts x 100+ elements smoothly.
- **D-09:** Consumer's original text displayed as a document. Spans linked to facts highlighted with semi-transparent background colors (one color per claim from categorical palette). Right margin shows small annotation chips with claim abbreviations. Click highlight or chip to expand detail popover.
- **D-10:** Overlapping annotations: stacked highlight layers (each claim's color at reduced opacity). Legend at top maps colors to claims. Click overlapping region to see all claims in detail popover. Shows where evidence is densest.
- **D-11:** "Trust But Verify" source links throughout ALL three views -- one click to ground truth using FactSourceSpan (message_id + start_char/end_char + source_page/source_paragraph).
- **D-12:** Tab bar above visualization area: Graph | Matrix | Narrative. View state preserved per tab via Zustand. URL reflects active tab (?view=graph). Switching tabs doesn't reset state.
- **D-13:** Shared filter context in Zustand: common filters (jurisdiction, claim, confidence threshold) apply across all views. View-specific extras persist across view switches.
- **D-14:** Every visualization has an accessible data table alternative (toggle via button or auto-detected by screen reader). ARIA live regions announce filter changes.
- **D-15:** Colorblind-safe categorical palette (tested against protanopia/deuteranopia). Shapes + patterns supplement color in matrix cells and graph nodes. Contrast ratios per WCAG 2.2 AA.
- **D-16:** Mobile adaptation: Graph touch pan/pinch-zoom with 44px hit targets, detail panel as bottom sheet. Matrix rotated to vertical with sticky first column. Narrative full-width with inline expansion.
- **D-17:** Per-view export: Graph -> SVG/PNG. Matrix -> CSV/PNG. Narrative -> annotated PDF. Exports respect current filter state.

### Claude's Discretion
- D3-force configuration (charge, collision, link distance values)
- Categorical color palette specific values (within colorblind-safe constraint)
- Detail panel layout and component structure
- Graph node label truncation strategy
- Matrix sort algorithm (by confidence, by source order, etc.)
- Canvas rendering implementation details

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FRONTEND-03 | Graph fact-mapping view: force-directed visualization of facts, claims, elements, and their relationships | D3-force simulation + React SVG wrapper with Canvas fallback; useForceSimulation hook pattern; Okabe-Ito palette |
| FRONTEND-04 | Matrix fact-mapping view: fact x element completeness matrix showing coverage | @tanstack/react-virtual bidirectional grid virtualization; 5-level color scale; sticky headers via CSS position:sticky |
| FRONTEND-05 | Narrative-anchored fact-mapping view: consumer's original narrative with overlaid analysis annotations | FactSourceSpan character offsets for highlight ranges; stacked semi-transparent backgrounds; popover detail on click |

</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| d3-force | 3.0.0 | Force-directed simulation engine | Industry standard for force layout; stable API since 2021; decoupled from rendering |
| d3-selection | 3.0.0 | DOM selection (Canvas fallback only) | Needed for Canvas tick rendering; minimal use in SVG mode |
| d3-zoom | 3.0.0 | Pan/zoom behavior for graph + Canvas | Standard D3 zoom with touch support; handles transform matrix |
| d3-drag | 3.0.0 | Node dragging in force graph | Standard D3 drag behavior; integrates with d3-force reheat |
| d3-scale | 4.0.2 | Map confidence scores to sizes/colors | Linear/ordinal scales for node sizing and color mapping |
| @tanstack/react-virtual | 3.13.23 | Virtual scrolling for matrix view | Already installed; supports row + column virtualization |
| html-to-image | 1.11.13 | SVG/DOM to PNG export | Lightweight; uses foreignObject SVG technique; no Canvas dependency |
| jspdf | 4.2.1 | PDF generation for narrative export | Client-side PDF; supports text with inline styling |
| zustand | 5.0.12 | Shared filter + view state | Already installed; extend with visualization slice |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @types/d3-force | 3.0.10 | TypeScript types for d3-force | Always (TypeScript project) |
| @types/d3-selection | 3.0.11 | TypeScript types for d3-selection | Always |
| @types/d3-zoom | 3.0.8 | TypeScript types for d3-zoom | Always |
| @types/d3-drag | 3.0.7 | TypeScript types for d3-drag | Always |
| @types/d3-scale | 4.0.9 | TypeScript types for d3-scale | Always |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| d3-force modular | Full d3 bundle (d3@7.9.0) | d3 full is ~500KB; modular imports save ~400KB. Use modular. |
| html-to-image | dom-to-image-more | dom-to-image-more is fork of abandoned dom-to-image; html-to-image is more actively maintained |
| jspdf | pdf-lib | pdf-lib is lower-level (no HTML rendering); jspdf has addHTML and text styling out of the box |
| Custom Canvas renderer | react-force-graph | react-force-graph bundles its own d3-force and Canvas renderer; less control over appearance, harder to match theme |

**Installation:**
```bash
cd frontend
npm install d3-force d3-selection d3-zoom d3-drag d3-scale html-to-image jspdf
npm install -D @types/d3-force @types/d3-selection @types/d3-zoom @types/d3-drag @types/d3-scale
```

**Bundle chunk configuration (vite.config.ts):**
```typescript
// Add to manualChunks:
'd3-vendor': ['d3-force', 'd3-selection', 'd3-zoom', 'd3-drag', 'd3-scale'],
'export-vendor': ['html-to-image', 'jspdf'],
```

**Version verification:** All versions confirmed via `npm view <pkg> version` on 2026-04-03.

## Architecture Patterns

### Recommended Project Structure
```
frontend/src/features/visualization/
  VisualizationPage.tsx          # Route entry: loads data, renders tab container
  store.ts                       # Zustand: shared filters + per-view state
  api.ts                         # React Query: fetch visualization data
  types.ts                       # Shared TypeScript types (nodes, edges, cells, etc.)
  hooks/
    useForceSimulation.ts        # D3-force simulation lifecycle hook
    useVisualizationData.ts      # Transform API response -> view-specific shapes
    useExport.ts                 # Per-view export logic (SVG/PNG/CSV/PDF)
  components/
    ViewTabs.tsx                 # Tab bar: Graph | Matrix | Narrative
    FilterBar.tsx                # Shared filter bar (jurisdiction, claim, confidence)
    DetailPanel.tsx              # Slide-out detail panel (shadcn Sheet)
    SourceSpanViewer.tsx         # "Trust but verify" source viewer
    AccessibleTable.tsx          # Data table fallback for screen readers
    graph/
      GraphView.tsx              # SVG graph container
      GraphCanvas.tsx            # Canvas fallback (>200 nodes)
      GraphNode.tsx              # SVG node component (shape by type)
      GraphLink.tsx              # SVG link component
    matrix/
      MatrixView.tsx             # Virtual grid container
      MatrixCell.tsx             # Confidence cell with color + number
      MatrixHeader.tsx           # Sticky claim/element headers
    narrative/
      NarrativeView.tsx          # Annotated text container
      HighlightSpan.tsx          # Stacked highlight component
      AnnotationChip.tsx         # Margin annotation chip
      NarrativeLegend.tsx        # Color-to-claim legend
```

### Pattern 1: D3-Force Simulation with React SVG Rendering

**What:** D3 owns the simulation (physics), React owns the DOM (rendering). The simulation runs in a `useEffect` with cleanup, outputting positioned node/link arrays to state. React renders `<circle>`, `<rect>`, `<line>` elements from that state.

**When to use:** For the graph view (D-01) with <200 nodes.

**Example:**
```typescript
// Source: d3-force API docs + React hooks pattern
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force'
import type { SimulationNodeDatum, SimulationLinkDatum } from 'd3-force'

interface GraphNode extends SimulationNodeDatum {
  id: string
  type: 'fact' | 'claim' | 'element' | 'gap'
  label: string
  confidence: number
}

interface GraphLink extends SimulationLinkDatum<GraphNode> {
  confidence: number
}

function useForceSimulation(
  nodes: GraphNode[],
  links: GraphLink[],
  width: number,
  height: number,
) {
  const [positions, setPositions] = useState<GraphNode[]>([])
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphLink> | null>(null)

  useEffect(() => {
    // D3-force mutates input arrays -- clone them
    const simNodes = nodes.map(n => ({ ...n }))
    const simLinks = links.map(l => ({ ...l }))

    const sim = forceSimulation(simNodes)
      .force('link', forceLink<GraphNode, GraphLink>(simLinks)
        .id(d => d.id)
        .distance(80))
      .force('charge', forceManyBody().strength(-200))
      .force('center', forceCenter(width / 2, height / 2))
      .force('collide', forceCollide<GraphNode>(d => 10 + d.confidence * 15))

    sim.on('tick', () => {
      setPositions([...simNodes])
    })

    simulationRef.current = sim

    return () => { sim.stop() }
  }, [nodes, links, width, height])

  return { positions, simulation: simulationRef }
}
```

### Pattern 2: Canvas Fallback for Large Graphs (>200 nodes)

**What:** When node count exceeds threshold, render to HTML5 Canvas instead of SVG. D3-force still runs the simulation; a Canvas 2D context draws nodes/links on each tick via `requestAnimationFrame`.

**When to use:** D-05: auto-switch at configurable threshold (default 200).

**Example:**
```typescript
// Canvas rendering in tick callback
function drawGraph(
  ctx: CanvasRenderingContext2D,
  nodes: GraphNode[],
  links: GraphLink[],
  transform: d3.ZoomTransform,
) {
  ctx.save()
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)
  ctx.translate(transform.x, transform.y)
  ctx.scale(transform.k, transform.k)

  // Draw links
  ctx.strokeStyle = '#999'
  ctx.lineWidth = 1
  for (const link of links) {
    const source = link.source as GraphNode
    const target = link.target as GraphNode
    ctx.beginPath()
    ctx.moveTo(source.x!, source.y!)
    ctx.lineTo(target.x!, target.y!)
    ctx.stroke()
  }

  // Draw nodes (shape by type)
  for (const node of nodes) {
    ctx.beginPath()
    const r = 5 + node.confidence * 10
    if (node.type === 'fact') {
      ctx.arc(node.x!, node.y!, r, 0, 2 * Math.PI) // circle
    } else if (node.type === 'claim') {
      roundRect(ctx, node.x! - r, node.y! - r * 0.7, r * 2, r * 1.4, 4)
    } else {
      drawDiamond(ctx, node.x!, node.y!, r) // element
    }
    ctx.fillStyle = getNodeColor(node)
    ctx.fill()
    if (node.type === 'gap') {
      ctx.setLineDash([4, 2])
      ctx.strokeStyle = '#666'
      ctx.stroke()
      ctx.setLineDash([])
    }
  }

  ctx.restore()
}
```

### Pattern 3: Bidirectional Virtual Grid (Matrix View)

**What:** Two `useVirtualizer` instances (one for rows, one for columns) sharing the same scroll container. Sticky headers via CSS `position: sticky`.

**When to use:** D-06, D-07, D-08: fact x element matrix with 500+ rows and 100+ columns.

**Example:**
```typescript
import { useVirtualizer } from '@tanstack/react-virtual'

function MatrixView({ facts, claimGroups }: MatrixProps) {
  const parentRef = useRef<HTMLDivElement>(null)

  const rowVirtualizer = useVirtualizer({
    count: facts.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 40,
    overscan: 10,
  })

  const columnVirtualizer = useVirtualizer({
    horizontal: true,
    count: totalElements,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80,
    overscan: 5,
  })

  return (
    <div ref={parentRef} className="overflow-auto h-full w-full">
      <div
        style={{
          height: rowVirtualizer.getTotalSize(),
          width: columnVirtualizer.getTotalSize(),
          position: 'relative',
        }}
      >
        {rowVirtualizer.getVirtualItems().map(vRow =>
          columnVirtualizer.getVirtualItems().map(vCol => (
            <MatrixCell
              key={`${vRow.index}-${vCol.index}`}
              style={{
                position: 'absolute',
                top: vRow.start,
                left: vCol.start,
                width: vCol.size,
                height: vRow.size,
              }}
              fact={facts[vRow.index]}
              element={getElement(vCol.index)}
              mapping={getMappingConfidence(vRow.index, vCol.index)}
            />
          ))
        )}
      </div>
    </div>
  )
}
```

### Pattern 4: Narrative Text Annotation with Overlapping Highlights

**What:** Render original consumer text with `<mark>` elements for each fact span. Overlapping spans use stacked semi-transparent backgrounds. Click expands a popover with claim details.

**When to use:** D-09, D-10: narrative-anchored view.

**Example:**
```typescript
// Build highlight ranges from FactSourceSpan data
interface AnnotationRange {
  start: number
  end: number
  claimIds: string[]
  color: string  // from categorical palette
}

function buildAnnotationRanges(
  spans: FactSourceSpan[],
  mappings: FactClaimMapping[],
  palette: string[],
): AnnotationRange[] {
  // Group spans by character position, merge overlapping
  // Each position can belong to multiple claims
  // Return sorted, non-overlapping segments with claim lists
}

function NarrativeView({ text, ranges }: NarrativeProps) {
  return (
    <div className="prose max-w-none">
      {renderAnnotatedText(text, ranges)}
      <NarrativeLegend claims={uniqueClaims} palette={palette} />
    </div>
  )
}
```

### Pattern 5: Zustand Filter Store with Per-View State

**What:** Single Zustand store with shared filters and per-view state slices. URL sync for active tab.

**When to use:** D-12, D-13: shared filters and view switching.

**Example:**
```typescript
import { create } from 'zustand'

interface VisualizationState {
  // Shared filters (D-13)
  activeView: 'graph' | 'matrix' | 'narrative'
  jurisdictionFilter: string | null
  claimFilter: string[] // selected claim IDs
  confidenceThreshold: number // 0-1 slider
  showGapsOnly: boolean

  // Per-view state (preserved across tab switches)
  graphState: { selectedNodeId: string | null; zoom: number; panX: number; panY: number }
  matrixState: { sortBy: 'confidence' | 'source_order'; selectedCell: [number, number] | null }
  narrativeState: { activeLayers: string[]; selectedSpanId: string | null }

  // Actions
  setActiveView: (v: 'graph' | 'matrix' | 'narrative') => void
  setJurisdiction: (j: string | null) => void
  setClaims: (c: string[]) => void
  setConfidenceThreshold: (t: number) => void
  // ... per-view setters
}
```

### Anti-Patterns to Avoid

- **Letting D3 manage React DOM:** Never use `d3.select().append()` inside React components for SVG mode. D3 should only manage the simulation. React renders the SVG elements from simulation state. D3 direct DOM manipulation is only acceptable in Canvas fallback mode.
- **Re-creating simulation on every render:** The simulation is expensive to initialize. Use `useRef` to hold the simulation reference and only re-create when the data shape changes (node/link count), not on every position update.
- **Putting simulation state in Zustand:** Tick-by-tick position updates (60fps) should NOT go through Zustand. Use local `useState` in the graph component. Zustand is for filters, selected node, and zoom level only.
- **Full D3 import:** `import * as d3 from 'd3'` pulls in ~500KB. Always use modular imports: `import { forceSimulation } from 'd3-force'`.
- **Virtualizing without sticky headers:** Without `position: sticky` on header rows/columns, users lose context in a large matrix. Always pin the first row (claim/element headers) and first column (fact labels).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Force-directed layout | Custom physics engine | d3-force | N-body simulation with Verlet integration; collision, charge, link forces with decades of tuning |
| Virtual scrolling | Custom windowing | @tanstack/react-virtual | Handles scroll position, overscan, dynamic sizing, bidirectional grids out of the box |
| Pan/zoom with touch | Custom transform math | d3-zoom | Handles pinch-zoom, wheel zoom, mouse drag, touch drag with momentum and bounds; works on both SVG and Canvas |
| Node dragging | Custom pointer events | d3-drag | Integrates with d3-force simulation reheat; handles touch + mouse; subject positioning |
| DOM-to-image export | Custom Canvas capture | html-to-image | Handles CSS styles, SVG elements, fonts, cross-origin images; well-tested edge cases |
| PDF generation | Custom PDF byte assembly | jspdf | Text layout, fonts, page breaks, inline styles; client-side without server round-trip |
| Color scales | Custom interpolation | d3-scale | Ordinal and linear scales with domain/range mapping; composable with color arrays |

**Key insight:** Visualization is a domain where subtle bugs (physics divergence, z-fighting, scroll jank, export fidelity) compound into unusable UIs. The D3 ecosystem has solved these problems over 15+ years.

## Common Pitfalls

### Pitfall 1: D3-Force Mutates Input Data
**What goes wrong:** D3-force simulation mutates the node and link arrays in place -- adding `x`, `y`, `vx`, `vy`, `index` properties to nodes, and replacing link source/target strings with object references.
**Why it happens:** D3-force is designed for imperative use, not React's immutable data flow.
**How to avoid:** Always clone node/link arrays before passing to `forceSimulation()`: `nodes.map(n => ({ ...n }))`. Never pass React state directly to the simulation.
**Warning signs:** `TypeError: Cannot add property x, object is not extensible` or stale/flickering positions.

### Pitfall 2: Simulation Not Stopping on Unmount
**What goes wrong:** D3-force simulation keeps running after component unmount, calling `setState` on unmounted component.
**Why it happens:** Missing cleanup in `useEffect`. D3 simulation runs on an internal timer.
**How to avoid:** Always return `() => { simulation.stop() }` from the `useEffect` that creates the simulation.
**Warning signs:** Console warning "Can't perform a React state update on an unmounted component" or increasing memory usage.

### Pitfall 3: Virtual Grid Losing Sticky Headers
**What goes wrong:** When using @tanstack/react-virtual for both rows and columns, sticky headers scroll away because they are inside the virtualized container.
**Why it happens:** Virtual items are absolutely positioned inside a relatively positioned container. CSS `position: sticky` doesn't work on absolutely positioned elements.
**How to avoid:** Render sticky headers OUTSIDE the virtualized area. Use a separate fixed header row and fixed first column that scroll in sync with the virtual container via `onScroll` event mirroring.
**Warning signs:** Headers scroll out of view when scrolling the matrix body.

### Pitfall 4: Overlapping Annotation Ranges Produce Invalid HTML
**What goes wrong:** Trying to nest `<mark>` elements for overlapping spans produces crossing tags (invalid HTML).
**Why it happens:** FactSourceSpan ranges from different claims can overlap at character positions.
**How to avoid:** Pre-process spans into non-overlapping segments. At each character position change point, create a new segment with the list of active claims at that position. Render each segment as a single `<span>` with stacked background colors (via CSS `background: linear-gradient(...)` or multiple box-shadows).
**Warning signs:** React hydration errors, broken highlighting, missing text.

### Pitfall 5: Canvas Mode Hit Testing
**What goes wrong:** Click events on Canvas don't automatically identify which node was clicked (unlike SVG where each element has its own event handler).
**Why it happens:** Canvas is a single bitmap surface -- no DOM elements to attach events to.
**How to avoid:** Implement hit testing: on click, iterate through nodes and check if click coordinates (adjusted for zoom transform) fall within node radius. Use `d3-quadtree` for O(log n) spatial lookup at 1000+ nodes.
**Warning signs:** Clicks don't register on nodes, or wrong node selected.

### Pitfall 6: Export Captures Wrong State
**What goes wrong:** PNG/SVG export captures the visualization before filters are applied, or captures stale data.
**Why it happens:** html-to-image captures the current DOM state. If filters trigger re-render that hasn't completed, the export is stale.
**How to avoid:** Ensure export runs after a `requestAnimationFrame` or `await new Promise(r => setTimeout(r, 0))` to let React flush pending state. For Canvas mode, export directly from the canvas element via `canvas.toDataURL()`.
**Warning signs:** Exported image doesn't match the screen.

### Pitfall 7: Analysis Results API Missing Visualization Data
**What goes wrong:** Frontend visualization components fail to render because the API doesn't return facts, fact-claim mappings, or source spans.
**Why it happens:** The current `/api/v1/analysis/{intake_id}/results` endpoint returns claims, gaps, and questions only. It imports `FactClaimMapping` but never queries it.
**How to avoid:** Extend the results endpoint (or create a dedicated `/api/v1/analysis/{intake_id}/visualization` endpoint) to return: extracted facts with source spans, fact-claim mappings with confidence scores, claims with elements, and gaps. This is a backend task that must be completed before frontend views can function.
**Warning signs:** Empty graph, empty matrix, no highlights in narrative view.

### Pitfall 8: Bundle Size Blow-Up from Full D3
**What goes wrong:** Importing the full `d3` package adds ~500KB to the bundle, blowing past the 200KB gzipped budget.
**Why it happens:** `d3` is an umbrella package that includes 30+ submodules, most unused.
**How to avoid:** Import only needed modules: `d3-force`, `d3-selection`, `d3-zoom`, `d3-drag`, `d3-scale`. Add a `d3-vendor` manual chunk in Vite config. Total D3 modular size is approximately 50-70KB minified.
**Warning signs:** Bundle analysis shows large d3 chunk with modules like `d3-geo`, `d3-contour`, `d3-hierarchy` that are not used.

## Code Examples

### Colorblind-Safe Categorical Palette (Okabe-Ito)

```typescript
// Source: Okabe & Ito (2002), recommended by Nature Methods
// Verified against protanopia/deuteranopia/tritanopia simulators
export const CATEGORICAL_PALETTE = [
  '#E69F00', // Orange -- facts
  '#56B4E9', // Sky Blue -- claims
  '#009E73', // Bluish Green -- elements
  '#D55E00', // Vermillion -- gaps
  '#0072B2', // Blue -- jurisdiction A
  '#CC79A7', // Reddish Purple -- jurisdiction B
  '#F0E442', // Yellow -- jurisdiction C (use with dark text)
  '#000000', // Black -- reserved / neutral
] as const

// Map node types to palette indices
export const NODE_TYPE_COLORS: Record<string, string> = {
  fact: CATEGORICAL_PALETTE[0],
  claim: CATEGORICAL_PALETTE[1],
  element: CATEGORICAL_PALETTE[2],
  gap: CATEGORICAL_PALETTE[3],
}

// 5-level confidence scale for matrix cells (D-07)
export const CONFIDENCE_SCALE = [
  { level: 'strong', min: 0.8, color: '#009E73', label: 'Strong' },    // Bluish Green
  { level: 'good', min: 0.6, color: '#56B4E9', label: 'Good' },       // Sky Blue
  { level: 'partial', min: 0.4, color: '#E69F00', label: 'Partial' },  // Orange
  { level: 'weak', min: 0.2, color: '#D55E00', label: 'Weak' },       // Vermillion
  { level: 'none', min: 0, color: '#cccccc', label: 'None' },         // Grey (gap)
] as const
```

### SVG Node Shapes by Type (D-02)

```typescript
// Render different SVG shapes based on node type
function GraphNodeSVG({ node, selected, ghosted }: GraphNodeProps) {
  const r = 6 + node.confidence * 14 // size proportional to confidence
  const fill = NODE_TYPE_COLORS[node.type]
  const opacity = ghosted ? 0.2 : 1
  const strokeDash = node.type === 'gap' ? '4,2' : undefined

  const common = {
    'data-node-id': node.id,
    role: 'img',
    'aria-label': `${node.type}: ${node.label}, confidence ${Math.round(node.confidence * 100)}%`,
    tabIndex: 0,
    style: { opacity, cursor: 'pointer' },
  }

  switch (node.type) {
    case 'fact':
      return <circle cx={node.x} cy={node.y} r={r} fill={fill}
        strokeDasharray={strokeDash} {...common} />
    case 'claim':
      return <rect x={node.x! - r} y={node.y! - r * 0.7} width={r * 2} height={r * 1.4}
        rx={4} fill={fill} strokeDasharray={strokeDash} {...common} />
    case 'element':
      return <polygon
        points={`${node.x},${node.y! - r} ${node.x! + r},${node.y} ${node.x},${node.y! + r} ${node.x! - r},${node.y}`}
        fill={fill} strokeDasharray={strokeDash} {...common} />
    case 'gap':
      return <circle cx={node.x} cy={node.y} r={r} fill="none"
        stroke={fill} strokeWidth={2} strokeDasharray="4,2" {...common} />
  }
}
```

### Matrix Cell with Confidence Color + Pattern (D-07)

```typescript
function MatrixCell({ mapping, onClick }: MatrixCellProps) {
  if (!mapping) {
    // Empty cell = gap (D-07: diagonal stripe pattern)
    return (
      <div
        className="w-full h-full flex items-center justify-center"
        style={{
          background: `repeating-linear-gradient(
            45deg,
            transparent,
            transparent 4px,
            hsl(var(--muted)) 4px,
            hsl(var(--muted)) 6px
          )`,
        }}
        aria-label="No mapping (gap)"
        role="gridcell"
      />
    )
  }

  const level = CONFIDENCE_SCALE.find(s => mapping.confidence >= s.min)!
  return (
    <button
      onClick={onClick}
      className="w-full h-full flex items-center justify-center text-xs font-mono"
      style={{ backgroundColor: `${level.color}20`, color: 'hsl(var(--foreground))' }}
      aria-label={`${level.label}: ${Math.round(mapping.confidence * 100)}% confidence`}
      role="gridcell"
    >
      {Math.round(mapping.confidence * 100)}
    </button>
  )
}
```

### Per-View Export (D-17)

```typescript
import { toSvg, toPng } from 'html-to-image'
import jsPDF from 'jspdf'

// Graph export: SVG or PNG
async function exportGraph(svgRef: HTMLElement, format: 'svg' | 'png') {
  const fn = format === 'svg' ? toSvg : toPng
  const dataUrl = await fn(svgRef, {
    backgroundColor: 'white',
    style: { transform: 'none' }, // reset zoom for export
  })
  downloadDataUrl(dataUrl, `analysis-graph.${format}`)
}

// Matrix export: CSV or PNG
function exportMatrixCSV(facts: Fact[], elements: Element[], mappings: Map<string, number>) {
  const header = ['Fact', ...elements.map(e => e.element_name)]
  const rows = facts.map(f => [
    f.assertion_text,
    ...elements.map(e => {
      const key = `${f.id}-${e.id}`
      return mappings.get(key)?.toString() ?? ''
    }),
  ])
  const csv = [header, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n')
  downloadBlob(new Blob([csv], { type: 'text/csv' }), 'analysis-matrix.csv')
}

// Narrative export: annotated PDF
async function exportNarrativePDF(text: string, annotations: AnnotationRange[]) {
  const doc = new jsPDF()
  doc.setFontSize(12)
  // Render text with inline annotations as footnotes
  let y = 20
  // ... text layout with page breaks
  doc.save('analysis-narrative.pdf')
}
```

### API Data Shape for Visualization

```typescript
// Expected response from extended /api/v1/analysis/{intake_id}/visualization
interface VisualizationData {
  run_id: number
  status: string

  facts: Array<{
    id: number
    assertion_text: string
    fact_type: string
    confidence: number
    source_spans: Array<{
      message_id: number
      start_char: number
      end_char: number
      page_number: number | null
      paragraph_index: number | null
      timestamp_start_sec: number | null
      timestamp_end_sec: number | null
    }>
  }>

  claims: Array<{
    id: number
    claim_name: string
    claim_type: string
    jurisdiction: string | null
    confidence: number
    rationale: string | null
    elements: Array<{
      id: number
      element_name: string
      element_description: string | null
      is_satisfied: boolean
      satisfaction_confidence: number | null
    }>
  }>

  mappings: Array<{
    id: number
    fact_id: number
    claim_id: number
    element_id: number | null
    confidence: number
    mapping_rationale: string | null
  }>

  gaps: Array<{
    id: number
    gap_type: string
    claim_id: number | null
    element_id: number | null
    description: string
    priority: number
    status: string
  }>

  // For narrative view: original messages text
  messages: Array<{
    id: number
    content: string
    sender_type: string
  }>
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Full D3 bundle import | Modular D3 imports (d3-force, d3-zoom, etc.) | D3 v4+ (2016) | ~80% bundle reduction; tree-shaking works with ESM |
| D3 manages DOM directly | D3 computes, React renders | Common since React 16 hooks (2019) | No DOM ownership conflicts; React DevTools works |
| react-window for virtualization | @tanstack/react-virtual | 2022-2023 | Better API, bidirectional support, maintained by TanStack |
| dom-to-image for export | html-to-image | 2021+ | Active maintenance; better cross-browser support |
| Server-side PDF (WeasyPrint) | Client-side jsPDF for simple exports | Ongoing | No server round-trip; but limited styling vs WeasyPrint |

**Deprecated/outdated:**
- `d3-force@2.x`: v3 is the latest stable (since 2021). No API breaking changes; v3 is pure ESM.
- `react-window`: Superseded by @tanstack/react-virtual for new projects. Still works but fewer features.
- `dom-to-image`: Abandoned. Use `dom-to-image-more` or `html-to-image` instead.

## Open Questions

1. **Visualization API endpoint scope**
   - What we know: Current `/api/v1/analysis/{intake_id}/results` does NOT return facts, mappings, or source spans. The FactClaimMapping model is imported but never queried.
   - What's unclear: Whether to extend the existing endpoint or create a new `/visualization` endpoint. Extending is simpler but may return too much data for non-visualization consumers.
   - Recommendation: Create a dedicated `/api/v1/analysis/{intake_id}/visualization` endpoint that returns the full data payload needed by all three views in a single request. This keeps the existing results endpoint lean.

2. **Canvas hit-testing precision at scale**
   - What we know: d3-quadtree provides O(log n) spatial lookup. At 1000+ nodes with varying sizes, hit regions need to match visual shapes (circles, diamonds, rounded rects).
   - What's unclear: Whether shape-aware hit testing (not just radius-based) is needed for Canvas mode.
   - Recommendation: Use bounding-box hit testing (sufficient for click targets on Canvas) plus visual hover feedback. Exact shape testing is unnecessary since Canvas nodes are small at high density.

3. **Narrative PDF export fidelity**
   - What we know: jsPDF can render text with basic styling. The narrative view has complex overlapping highlights and margin annotations.
   - What's unclear: How well jsPDF can reproduce the highlighted text appearance from the DOM.
   - Recommendation: For MVP, export plain text with claim annotations as footnotes (not pixel-perfect highlight reproduction). If higher fidelity is needed later, use server-side WeasyPrint (already in the project for Phase 7 PDF exports).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Frontend build | Yes | (project already builds) | -- |
| npm | Package install | Yes | (project already uses npm) | -- |
| d3-force | Graph view | Not yet installed | 3.0.0 on npm | Must install |
| @tanstack/react-virtual | Matrix view | Yes | 3.13.23 | -- |
| html-to-image | SVG/PNG export | Not yet installed | 1.11.13 on npm | Must install |
| jspdf | PDF export | Not yet installed | 4.2.1 on npm | Must install |
| Vite | Dev server + build | Yes | 6.x | -- |
| Vitest | Unit tests | Yes | 4.x | -- |

**Missing dependencies with no fallback:**
- d3-force, d3-selection, d3-zoom, d3-drag, d3-scale (must install for graph view)
- html-to-image (must install for PNG/SVG export)
- jspdf (must install for narrative PDF export)

**Missing dependencies with fallback:**
- None -- all missing dependencies must be installed, no viable alternatives.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest 4.x + @testing-library/react 16.x |
| Config file | `frontend/vitest.config.ts` |
| Quick run command | `cd frontend && npx vitest run --reporter=verbose` |
| Full suite command | `cd frontend && npm run test:run` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FRONTEND-03 | Force graph renders nodes and links from data | unit | `cd frontend && npx vitest run src/features/visualization/components/graph/GraphView.test.tsx -x` | Wave 0 |
| FRONTEND-03 | useForceSimulation produces positioned nodes | unit | `cd frontend && npx vitest run src/features/visualization/hooks/useForceSimulation.test.ts -x` | Wave 0 |
| FRONTEND-03 | Canvas fallback activates above threshold | unit | `cd frontend && npx vitest run src/features/visualization/components/graph/GraphCanvas.test.tsx -x` | Wave 0 |
| FRONTEND-04 | Matrix renders cells with confidence colors | unit | `cd frontend && npx vitest run src/features/visualization/components/matrix/MatrixView.test.tsx -x` | Wave 0 |
| FRONTEND-04 | Virtual scrolling handles 500+ rows | unit | `cd frontend && npx vitest run src/features/visualization/components/matrix/MatrixView.test.tsx -x` | Wave 0 |
| FRONTEND-05 | Narrative highlights text spans correctly | unit | `cd frontend && npx vitest run src/features/visualization/components/narrative/NarrativeView.test.tsx -x` | Wave 0 |
| FRONTEND-05 | Overlapping spans produce correct segments | unit | `cd frontend && npx vitest run src/features/visualization/components/narrative/HighlightSpan.test.tsx -x` | Wave 0 |
| ALL | Tab switching preserves per-view state | unit | `cd frontend && npx vitest run src/features/visualization/components/ViewTabs.test.tsx -x` | Wave 0 |
| ALL | Shared filter state updates all views | unit | `cd frontend && npx vitest run src/features/visualization/store.test.ts -x` | Wave 0 |
| ALL | Accessible data table fallback renders | unit | `cd frontend && npx vitest run src/features/visualization/components/AccessibleTable.test.tsx -x` | Wave 0 |
| ALL | Export produces correct output per view | unit | `cd frontend && npx vitest run src/features/visualization/hooks/useExport.test.ts -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd frontend && npx vitest run --reporter=verbose`
- **Per wave merge:** `cd frontend && npm run test:run`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `frontend/src/features/visualization/` directory -- entire feature directory (new)
- [ ] All test files listed above -- none exist yet
- [ ] MSW handlers for `/api/v1/analysis/:id/visualization` endpoint
- [ ] Test fixtures: mock visualization data (facts, claims, elements, mappings, gaps, messages)
- [ ] jsdom Canvas context mock (for Canvas fallback tests)

## Sources

### Primary (HIGH confidence)
- npm registry: d3-force@3.0.0, d3-selection@3.0.0, d3-zoom@3.0.0, d3-drag@3.0.0, d3-scale@4.0.2 -- version verification
- npm registry: @tanstack/react-virtual@3.13.23 -- already installed, version verified
- npm registry: html-to-image@1.11.13, jspdf@4.2.1 -- version verification
- Project source code: `backend/app/models/analysis.py`, `backend/app/models/fact.py` -- data model structure
- Project source code: `backend/app/routers/analysis.py` -- current API endpoint gaps identified
- Project source code: `frontend/package.json`, `frontend/vite.config.ts` -- existing stack and bundle config
- Project source code: `frontend/src/styles/globals.css` -- existing CSS custom properties and theme system

### Secondary (MEDIUM confidence)
- [D3.js force-directed graph implementation guide (2025)](https://dev.to/nigelsilonero/how-to-implement-a-d3js-force-directed-graph-in-2025-5cl1) -- React+D3 integration patterns
- [React + D3 force graphs + TypeScript guide](https://medium.com/@qdangdo/visualizing-connections-a-guide-to-react-d3-force-graphs-typescript-74b7af728c90) -- TypeScript patterns
- [TanStack Virtual docs](https://tanstack.com/virtual/latest) -- bidirectional virtualization support
- [Building Sticky Headers with TanStack Virtualizer](https://mashuktamim.medium.com/building-sticky-headers-and-columns-with-tanstack-virtualizer-react-a-complete-guide-12123ef75334) -- sticky header pattern
- [Okabe-Ito palette complete reference](https://conceptviz.app/blog/okabe-ito-palette-hex-codes-complete-reference) -- exact hex codes
- [David Nichols Coloring for Colorblindness](https://davidmathlogic.com/colorblind/) -- palette testing methodology
- [html-to-image npm](https://www.npmjs.com/package/html-to-image) -- export library capabilities
- [D3 official force docs](https://d3js.org/d3-force) -- simulation API reference
- [D3 Network Graphs Canvas rendering](https://www.antstack.com/blog/leveling-up-your-d3-network-graphs-from-simple-canvas-to-interactive-powerhouse/) -- Canvas performance patterns

### Tertiary (LOW confidence)
- None -- all findings verified against multiple sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries verified on npm with current versions; D3 modular approach is well-established
- Architecture: HIGH -- patterns verified against multiple implementation guides and existing project conventions
- Pitfalls: HIGH -- pitfalls 1-2 (D3 mutation, simulation cleanup) are universally documented; pitfall 7 (missing API data) verified by reading actual source code
- API gap: HIGH -- confirmed by direct code inspection of `backend/app/routers/analysis.py`

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (stable domain; D3 v3 is unchanging; React patterns mature)
