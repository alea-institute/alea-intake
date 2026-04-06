import { useNavigate } from 'react-router-dom'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useTranslation } from 'react-i18next'
import type { IntakeSummary } from '../api'

interface Props {
  intakes: IntakeSummary[]
}

const STATUS_LABEL: Record<IntakeSummary['status'], string> = {
  new: 'New',
  in_progress: 'In progress',
  complete: 'Complete',
  referred: 'Referred',
  abandoned: 'Abandoned',
}

export function IntakeTable({ intakes }: Props) {
  const navigate = useNavigate()
  const { t } = useTranslation('dashboard')

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t('col.matterId', 'Matter')}</TableHead>
          <TableHead>{t('col.consumer', 'Consumer')}</TableHead>
          <TableHead className="hidden md:table-cell">
            {t('col.area', 'Area')}
          </TableHead>
          <TableHead className="hidden lg:table-cell">
            {t('col.jurisdiction', 'Jurisdiction')}
          </TableHead>
          <TableHead>{t('col.status', 'Status')}</TableHead>
          <TableHead className="hidden md:table-cell">
            {t('col.lastActivity', 'Last activity')}
          </TableHead>
          <TableHead className="text-right">
            {t('col.completeness', 'Complete')}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {intakes.map((i) => (
          <TableRow
            key={i.id}
            onClick={() => navigate(`/intake/${i.id}/output`)}
            className="cursor-pointer hover:bg-secondary min-h-[44px]"
            tabIndex={0}
            role="button"
            aria-label={t('row.open', 'Open intake {{matter}}', {
              matter: i.matterId,
            })}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                navigate(`/intake/${i.id}/output`)
              }
            }}
          >
            <TableCell className="font-mono text-[14px]">
              {i.matterId}
            </TableCell>
            <TableCell>{i.consumerName}</TableCell>
            <TableCell className="hidden md:table-cell">
              {i.areaOfLaw ?? '\u2014'}
            </TableCell>
            <TableCell className="hidden lg:table-cell">
              {i.jurisdiction ?? '\u2014'}
            </TableCell>
            <TableCell>{STATUS_LABEL[i.status]}</TableCell>
            <TableCell className="hidden md:table-cell">
              {new Date(i.lastActivity).toLocaleDateString()}
            </TableCell>
            <TableCell className="text-right">
              {Math.round(i.completeness * 100)}%
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
