import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface Props {
  illustration?: ReactNode
  heading: string
  body?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ illustration, heading, body, action, className }: Props) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center py-[64px] px-[16px] gap-[16px] max-w-md mx-auto',
        className
      )}
    >
      {illustration && (
        <div className="w-60 h-60 max-[768px]:w-40 max-[768px]:h-40 opacity-40">
          {illustration}
        </div>
      )}
      <h2 className="font-display text-[28px] font-semibold leading-[1.2] text-foreground">
        {heading}
      </h2>
      {body && (
        <p className="font-body text-[16px] leading-[1.5] text-muted-foreground">
          {body}
        </p>
      )}
      {action && <div className="mt-[16px]">{action}</div>}
    </div>
  )
}
