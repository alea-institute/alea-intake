import { useEffect, useRef, type KeyboardEvent } from 'react'
import { cn } from '@/lib/utils'
import { usePracticeAreas } from '../hooks/usePracticeAreas'
import type { PracticeArea } from '../types'

interface Props {
  selectedId: string | null
  onSelect: (id: string | null) => void
}

/** Sentinel id used by the "Generic" chip in the radiogroup. */
const GENERIC_KEY = '__generic__'

/**
 * Horizontal radiogroup of practice-area chips rendered above the welcome
 * card on the intake landing. The first chip is "Generic" — selecting it
 * is equivalent to choosing no practice (id = null).
 *
 * UX:
 *  - Active chip is intentionally loud at projector distance: filled
 *    accent background + scale-up. Not subtle.
 *  - Loading: skeleton chips, not a spinner — keeps layout stable on
 *    first paint.
 *  - Failure: render nothing. The intake must always be startable; a
 *    failed taxonomy fetch must never block the user.
 *  - Disclaimer (when present on the selected practice) renders inline
 *    below the row in a muted callout.
 *
 * A11y: `role="radiogroup"` with `role="radio"` + `aria-checked` per chip.
 * Arrow keys move focus between chips and select; Home/End jump to ends.
 */
export function PracticeAreaChips({ selectedId, onSelect }: Props) {
  const { data: practiceAreas, isLoading, isError } = usePracticeAreas()

  // Refs for roving-focus arrow-key navigation
  const chipRefs = useRef<Map<string, HTMLButtonElement | null>>(new Map())

  if (isError) return null
  if (isLoading) return <PracticeAreaChipsSkeleton />
  // Empty registry: don't render the row at all — same logic as failure.
  if (!practiceAreas || practiceAreas.length === 0) return null

  const orderedKeys: string[] = [GENERIC_KEY, ...practiceAreas.map((p) => p.id)]
  const selectedKey = selectedId ?? GENERIC_KEY
  const selectedArea: PracticeArea | undefined = practiceAreas.find(
    (p) => p.id === selectedId,
  )

  function handleKeyDown(e: KeyboardEvent<HTMLButtonElement>, currentKey: string) {
    const idx = orderedKeys.indexOf(currentKey)
    if (idx === -1) return
    let nextIdx = idx
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      nextIdx = (idx + 1) % orderedKeys.length
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      nextIdx = (idx - 1 + orderedKeys.length) % orderedKeys.length
    } else if (e.key === 'Home') {
      nextIdx = 0
    } else if (e.key === 'End') {
      nextIdx = orderedKeys.length - 1
    } else if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault()
      onSelect(currentKey === GENERIC_KEY ? null : currentKey)
      return
    } else {
      return
    }
    e.preventDefault()
    const nextKey = orderedKeys[nextIdx]
    const nextEl = chipRefs.current.get(nextKey)
    nextEl?.focus()
    onSelect(nextKey === GENERIC_KEY ? null : nextKey)
  }

  return (
    <div className="w-full">
      <div
        role="radiogroup"
        aria-label="Practice area"
        className="flex gap-xs overflow-x-auto pb-xs scrollbar-thin"
      >
        <Chip
          key={GENERIC_KEY}
          label="Generic"
          isSelected={selectedKey === GENERIC_KEY}
          tabIndex={selectedKey === GENERIC_KEY ? 0 : -1}
          onClick={() => onSelect(null)}
          onKeyDown={(e) => handleKeyDown(e, GENERIC_KEY)}
          buttonRef={(el) => chipRefs.current.set(GENERIC_KEY, el)}
        />
        {practiceAreas.map((p) => (
          <Chip
            key={p.id}
            label={p.display_name}
            isSelected={selectedKey === p.id}
            tabIndex={selectedKey === p.id ? 0 : -1}
            onClick={() => onSelect(p.id)}
            onKeyDown={(e) => handleKeyDown(e, p.id)}
            buttonRef={(el) => chipRefs.current.set(p.id, el)}
          />
        ))}
      </div>
      {selectedArea?.disclaimer ? (
        <p
          role="note"
          className="mt-xs px-md py-sm rounded-md bg-muted text-muted-foreground text-[14px] leading-[1.5] border border-border"
        >
          {selectedArea.disclaimer}
        </p>
      ) : null}
    </div>
  )
}

interface ChipProps {
  label: string
  isSelected: boolean
  tabIndex: number
  onClick: () => void
  onKeyDown: (e: KeyboardEvent<HTMLButtonElement>) => void
  buttonRef: (el: HTMLButtonElement | null) => void
}

function Chip({
  label,
  isSelected,
  tabIndex,
  onClick,
  onKeyDown,
  buttonRef,
}: ChipProps) {
  // When the active selection changes, ensure the freshly-active chip's
  // ref is cached so arrow keys can refocus reliably.
  const localRef = useRef<HTMLButtonElement | null>(null)
  useEffect(() => {
    buttonRef(localRef.current)
  })

  return (
    <button
      ref={localRef}
      type="button"
      role="radio"
      aria-checked={isSelected}
      tabIndex={tabIndex}
      onClick={onClick}
      onKeyDown={onKeyDown}
      className={cn(
        // Base
        'shrink-0 inline-flex items-center justify-center',
        'min-h-[44px] px-md rounded-full font-display text-[15px] font-medium',
        'transition-all duration-200 ease-out',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        'focus-visible:ring-offset-background',
        isSelected
          ? // Active: filled accent, scale-up, ring-style outer halo for projector clarity
            'bg-accent text-accent-foreground border border-accent shadow-[0_0_0_3px_hsl(var(--accent)/0.18)] scale-[1.04]'
          : // Resting: outlined chip on card surface
            'bg-card text-card-foreground border border-border hover:bg-secondary hover:border-accent/40',
      )}
    >
      {label}
    </button>
  )
}

function PracticeAreaChipsSkeleton() {
  return (
    <div
      role="radiogroup"
      aria-label="Practice area"
      aria-busy="true"
      className="flex gap-xs overflow-x-auto pb-xs"
    >
      {[112, 152, 132, 144].map((w, i) => (
        <div
          key={i}
          className="shrink-0 h-[44px] rounded-full bg-primary/10 animate-pulse"
          style={{ width: w }}
          aria-hidden="true"
        />
      ))}
    </div>
  )
}
