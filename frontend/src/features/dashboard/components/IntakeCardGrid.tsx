import { useNavigate } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { IntakeSummary } from '../api'

interface Props {
  intakes: IntakeSummary[]
}

export function IntakeCardGrid({ intakes }: Props) {
  const navigate = useNavigate()
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-[16px]" role="list">
      {intakes.map((i) => (
        <Card
          key={i.id}
          role="listitem"
          tabIndex={0}
          className="p-[16px] cursor-pointer hover:shadow-md focus:ring-2 focus:ring-ring outline-none"
          onClick={() => navigate(`/intake/${i.id}/output`)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') navigate(`/intake/${i.id}/output`)
          }}
        >
          <div className="flex justify-between items-start mb-[8px]">
            <span className="font-mono text-[14px] text-muted-foreground">
              {i.matterId}
            </span>
            <Badge>{i.status}</Badge>
          </div>
          <h3 className="font-display text-[20px] font-semibold mb-[4px]">
            {i.consumerName}
          </h3>
          <p className="font-body text-[14px] text-muted-foreground">
            {i.areaOfLaw ?? 'Area TBD'} &bull; {i.jurisdiction ?? '\u2014'}
          </p>
          <div className="mt-[8px] font-body text-[14px]">
            {Math.round(i.completeness * 100)}% complete
          </div>
        </Card>
      ))}
    </div>
  )
}
