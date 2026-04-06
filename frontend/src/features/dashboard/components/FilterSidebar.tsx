import { useTranslation } from 'react-i18next'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import type { IntakeFilters } from '../api'

interface Props {
  filters: IntakeFilters
  onChange: (next: IntakeFilters) => void
}

const STATUSES = ['new', 'in_progress', 'complete', 'referred', 'abandoned'] as const

export function FilterSidebar({ filters, onChange }: Props) {
  const { t } = useTranslation('dashboard')
  return (
    <aside className="w-60 border-r border-border p-[16px] space-y-[16px] hidden md:block">
      <h2 className="font-display text-[20px] font-semibold">
        {t('filters.heading', 'Filters')}
      </h2>
      <div className="space-y-[8px]">
        <label className="font-body text-[14px] block">
          {t('filters.search', 'Search')}
        </label>
        <Input
          value={filters.q ?? ''}
          onChange={(e) => onChange({ ...filters, q: e.target.value || undefined })}
          placeholder={t('filters.searchPlaceholder', 'Name or matter ID')}
          className="min-h-[44px]"
        />
      </div>
      <div className="space-y-[8px]">
        <label className="font-body text-[14px] block" htmlFor="status-filter">
          {t('filters.status', 'Status')}
        </label>
        <Select
          value={filters.status?.[0] ?? 'all'}
          onValueChange={(v) =>
            onChange({ ...filters, status: v === 'all' ? undefined : [v] })
          }
        >
          <SelectTrigger id="status-filter" className="min-h-[44px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('filters.all', 'All')}</SelectItem>
            {STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {s.replace('_', ' ')}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </aside>
  )
}
