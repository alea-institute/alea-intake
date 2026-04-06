/**
 * Source span viewer -- "trust but verify" component (D-11).
 *
 * Renders source spans as links to the original message text with the
 * relevant portion highlighted. Shows page/paragraph for documents,
 * timestamp for voice transcripts.
 */

import type { VisualizationMessage, VisualizationSourceSpan } from '../types'

interface SourceSpanViewerProps {
  sourceSpans: VisualizationSourceSpan[]
  messages: VisualizationMessage[]
}

export function SourceSpanViewer({ sourceSpans, messages }: SourceSpanViewerProps) {
  if (sourceSpans.length === 0) {
    return <p className="text-sm text-muted-foreground italic">No source spans available</p>
  }

  const messageMap = new Map(messages.map((m) => [m.id, m]))

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-semibold text-foreground">Source Evidence</h4>
      {sourceSpans.map((span, idx) => {
        const message = messageMap.get(span.message_id)
        if (!message) return null

        const content = message.content
        const before = content.slice(Math.max(0, span.start_char - 30), span.start_char)
        const highlighted = content.slice(span.start_char, span.end_char)
        const after = content.slice(span.end_char, span.end_char + 30)

        const hasLocation = span.page_number != null || span.timestamp_start_sec != null

        return (
          <div
            key={`${span.message_id}-${span.start_char}-${idx}`}
            className="rounded-md border border-border bg-card p-3 text-sm"
          >
            {/* Location metadata */}
            {hasLocation && (
              <div className="mb-1 flex gap-3 text-xs text-muted-foreground">
                {span.page_number != null && (
                  <span>
                    Page {span.page_number}
                    {span.paragraph_index != null && `, Para {span.paragraph_index}`}
                  </span>
                )}
                {span.timestamp_start_sec != null && (
                  <span>
                    {formatTimestamp(span.timestamp_start_sec)}
                    {span.timestamp_end_sec != null && ` - ${formatTimestamp(span.timestamp_end_sec)}`}
                  </span>
                )}
              </div>
            )}

            {/* Highlighted excerpt */}
            <p className="leading-relaxed">
              {before && <span className="text-muted-foreground">...{before}</span>}
              <mark className="rounded bg-yellow-200/70 px-0.5 font-medium dark:bg-yellow-800/50">
                {highlighted}
              </mark>
              {after && <span className="text-muted-foreground">{after}...</span>}
            </p>
          </div>
        )
      })}
    </div>
  )
}

function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
