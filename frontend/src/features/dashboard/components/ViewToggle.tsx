import { Table2, LayoutGrid } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useTranslation } from 'react-i18next'

export type DashboardView = 'table' | 'cards'
interface Props {
  view: DashboardView
  onChange: (v: DashboardView) => void
}

export function ViewToggle({ view, onChange }: Props) {
  const { t } = useTranslation('dashboard')
  return (
    <div
      className="inline-flex border border-border rounded"
      role="radiogroup"
      aria-label={t('view.label', 'Display mode')}
    >
      <Button
        variant="ghost"
        role="radio"
        aria-checked={view === 'table'}
        onClick={() => onChange('table')}
        className={cn(
          'min-h-[44px] min-w-[44px] rounded-none rounded-l',
          view === 'table' && 'bg-primary text-primary-foreground hover:bg-primary'
        )}
        aria-label={t('view.table', 'Table view')}
      >
        <Table2 className="h-4 w-4" aria-hidden="true" />
      </Button>
      <Button
        variant="ghost"
        role="radio"
        aria-checked={view === 'cards'}
        onClick={() => onChange('cards')}
        className={cn(
          'min-h-[44px] min-w-[44px] rounded-none rounded-r',
          view === 'cards' && 'bg-primary text-primary-foreground hover:bg-primary'
        )}
        aria-label={t('view.cards', 'Card view')}
      >
        <LayoutGrid className="h-4 w-4" aria-hidden="true" />
      </Button>
    </div>
  )
}
