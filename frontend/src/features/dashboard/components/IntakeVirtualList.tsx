import { useVirtualizer } from '@tanstack/react-virtual'
import { useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import type { IntakeSummary } from '../api'

interface Props {
  intakes: IntakeSummary[]
}

export function IntakeVirtualList({ intakes }: Props) {
  const parentRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const rowVirtualizer = useVirtualizer({
    count: intakes.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 72,
    overscan: 8,
    useFlushSync: false, // Pitfall 5 -- React 19
  })

  return (
    <div
      ref={parentRef}
      className="h-[600px] overflow-auto"
      role="list"
      aria-label="Intakes"
    >
      <div style={{ height: rowVirtualizer.getTotalSize(), position: 'relative' }}>
        {rowVirtualizer.getVirtualItems().map((v) => {
          const intake = intakes[v.index]
          return (
            <button
              key={v.key}
              role="listitem"
              type="button"
              onClick={() => navigate(`/intake/${intake.id}/output`)}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                transform: `translateY(${v.start}px)`,
                width: '100%',
                height: `${v.size}px`,
              }}
              className="px-[16px] py-[8px] border-b border-border text-left hover:bg-secondary focus:ring-2 focus:ring-ring outline-none"
            >
              <div className="flex justify-between items-center">
                <div>
                  <div className="font-mono text-[14px]">{intake.matterId}</div>
                  <div className="font-body text-[16px]">{intake.consumerName}</div>
                </div>
                <div className="text-right text-[14px] text-muted-foreground">
                  {Math.round(intake.completeness * 100)}%
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
