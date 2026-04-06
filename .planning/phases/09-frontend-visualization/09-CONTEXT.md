# Phase 9: Frontend Visualization - Context

**Gathered:** 2026-04-06
**Status:** Ready for UI-phase / planning

<domain>
## Phase Boundary

Three specialized fact-mapping visualization views — force-directed graph, fact×element completeness matrix, and narrative-anchored annotations — with shared filter context, view-switching tabs, per-view export, "trust but verify" source links, accessible data table fallbacks, and mobile-adapted layouts. All views inherit Phase 8's theme system.

</domain>

<decisions>
## Implementation Decisions

### Graph View (FRONTEND-03)
- **D-01:** D3-force + thin React wrapper (SVG). Force simulation via D3, React handles DOM and event binding. Most flexible, best performance for typical legal analysis graphs (100-500 nodes).
- **D-02:** Node encoding: shape + color by type (Facts=circles, Claims=rounded rectangles, Elements=diamonds), size proportional to confidence score. Low-confidence nodes smaller/lighter. Gaps highlighted with dashed borders. Colors from theme categorical palette.
- **D-03:** Click node opens a slide-out detail panel showing: node type info (fact text, claim description, element requirements), connected edges with confidence, source spans, authorities. Panel stays open while exploring. Professional can annotate from panel.
- **D-04:** Filter bar: toggle node types (facts/claims/elements), jurisdiction selector, confidence threshold slider, gap-status highlight. Filtered-out nodes fade to ghosted (stay visible for spatial context).
- **D-05:** SVG for <200 nodes (crisp, accessible, per-node events). Auto-switch to HTML5 Canvas for >200 nodes (60fps at 1000+). Canvas mode loses per-node ARIA. Threshold configurable.

### Matrix View (FRONTEND-04)
- **D-06:** Facts as rows, elements grouped by claim as columns. Column headers are collapsible per claim. Gap columns highlighted with warning indicator.
- **D-07:** Cells: 5-level color scale (strong/good/partial/weak/none) matching theme + subtle numeric confidence scores visible in each cell. Hover shows: confidence score, mapping rationale, source span. Click opens same detail panel as graph view. Empty cells (gaps) have diagonal stripe pattern.
- **D-08:** Virtual scrolling (@tanstack/react-virtual) for both rows and columns + sticky claim headers and fact labels. Handles 500+ facts × 100+ elements smoothly.

### Narrative-Anchored View (FRONTEND-05)
- **D-09:** Consumer's original text displayed as a document. Spans linked to facts highlighted with semi-transparent background colors (one color per claim from categorical palette). Right margin shows small annotation chips with claim abbreviations. Click highlight or chip to expand detail popover.
- **D-10:** Overlapping annotations: stacked highlight layers (each claim's color at reduced opacity). Legend at top maps colors to claims. Click overlapping region to see all claims in detail popover. Shows where evidence is densest.

### "Trust But Verify" Source Links
- **D-11:** Every fact/claim/element throughout ALL three views links directly to its source ground truth. User clicks → system immediately shows the highlighted portion of the original source: interview transcript (with character offsets), uploaded document section (with page/paragraph), or voice transcript (with timestamp). Uses Phase 3's FactSourceSpan (message_id + start_char/end_char + source_page/source_paragraph). One click to ground truth, always.

### View Switching & Shared Data Layer
- **D-12:** Tab bar above visualization area: Graph | Matrix | Narrative. View state (selected node, filters, zoom) preserved per tab via Zustand. URL reflects active tab (?view=graph). Switching tabs doesn't reset state.
- **D-13:** Shared filter context in Zustand: common filters (jurisdiction, claim, confidence threshold) apply across all views. View-specific extras: graph has node-type toggles, matrix has row/column sorting, narrative has annotation-layer toggles. Filters persist across view switches.

### Accessibility
- **D-14:** Every visualization has an accessible data table alternative (toggle via button or auto-detected by screen reader). Graph → table of nodes + edges. Matrix → standard HTML table. Narrative → text with footnote-style annotations. ARIA live regions announce filter changes.
- **D-15:** Colorblind-safe categorical palette (tested against protanopia/deuteranopia). Shapes + patterns supplement color in matrix cells and graph nodes. Contrast ratios per WCAG 2.2 AA.

### Mobile Adaptation
- **D-16:** Graph: touch-enabled pan/pinch-zoom, larger node hit targets (44px), detail panel as bottom sheet. Matrix: rotated to vertical (claims as rows, horizontal scroll for facts), sticky first column. Narrative: full-width text, annotations as inline expansion (not margin chips). All three views usable on mobile.

### Visualization Export
- **D-17:** Per-view export: Graph → SVG (scalable) or PNG (raster). Matrix → CSV (data) or PNG (visual). Narrative → annotated PDF (highlighted text + footnotes). Export button in each view's toolbar. Exports respect current filter state.

### Claude's Discretion
- D3-force configuration (charge, collision, link distance values)
- Categorical color palette specific values (within colorblind-safe constraint)
- Detail panel layout and component structure
- Graph node label truncation strategy
- Matrix sort algorithm (by confidence, by source order, etc.)
- Canvas rendering implementation details

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Dependencies
- `.planning/phases/08-frontend-application/08-CONTEXT.md` — Frontend architecture (Zustand, React Query, shadcn, themes, a11y)
- `.planning/phases/08-frontend-application/08-UI-SPEC.md` — Design tokens, typography, colors, spacing
- `.planning/phases/04-core-analysis-pipeline/04-CONTEXT.md` — Analysis models (claims, elements, mappings, gaps)
- `.planning/phases/03-input-narrative-capture/03-CONTEXT.md` — FactSourceSpan for source linking

### Existing Code
- `frontend/src/features/chat/` — Chat components, WebSocket hook, Zustand stores
- `frontend/src/features/output/` — Output display, MarkdownMemo, ExportMenu
- `frontend/src/shared/components/ThemeProvider.tsx` — Theme system with data-theme attributes
- `backend/app/models/analysis.py` — AnalysisClaim, ClaimElement, FactClaimMapping, AnalysisGap
- `backend/app/models/fact.py` — ExtractedFact, FactSourceSpan (source span offsets)
- `backend/app/routers/analysis.py` — Analysis REST API (results endpoint)

### Requirements
- `.planning/REQUIREMENTS.md` — FRONTEND-03, FRONTEND-04, FRONTEND-05

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **@tanstack/react-virtual**: Already installed — reuse for matrix virtualization
- **shadcn/ui Sheet component**: Already installed — reuse for detail side panel
- **Theme CSS variables**: Three-theme system already built — visualizations use theme colors
- **React Query**: Already configured — use for fetching analysis results
- **Zustand**: Already used for chat/auth stores — extend for visualization filter state
- **ExportMenu pattern**: Already built in Phase 8 — reuse for per-view export

### Integration Points
- Visualizations render on the output/analysis page (new tab or subsection)
- Analysis results fetched via existing `/api/v1/analysis/{intake_id}/results` endpoint
- Source spans link to existing message/document/transcript content
- Filter state shared via Zustand across tab switches

</code_context>

<specifics>
## Specific Ideas

- "Trust but verify" is the core UX principle — every data point one click from ground truth source text
- Stacked overlapping annotations show evidence density visually
- SVG→Canvas auto-switch at 200 nodes preserves accessibility for typical cases while handling edge cases
- Matrix cells show both color AND number for scan-ability + precision

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 09-frontend-visualization*
*Context gathered: 2026-04-06*
