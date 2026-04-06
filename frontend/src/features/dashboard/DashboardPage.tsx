import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useTheme } from '@/shared/components/ThemeProvider'
import { EmptyState } from '@/shared/components/EmptyState'
import { useIntakes } from './hooks/useIntakes'
import { IntakeTable } from './components/IntakeTable'
import { IntakeCardGrid } from './components/IntakeCardGrid'
import { IntakeVirtualList } from './components/IntakeVirtualList'
import { FilterSidebar } from './components/FilterSidebar'
import { ViewToggle, type DashboardView } from './components/ViewToggle'
import type { IntakeFilters } from './api'

const VIRTUAL_THRESHOLD = 100

export function DashboardPage() {
  const { t } = useTranslation('dashboard')
  const { theme } = useTheme()
  const navigate = useNavigate()
  const [view, setView] = useState<DashboardView>('table')
  const [filters, setFilters] = useState<IntakeFilters>({})
  const { data, isLoading } = useIntakes(filters)
  const intakes = data?.items ?? []

  return (
    <div className="flex flex-1 min-h-0">
      <FilterSidebar filters={filters} onChange={setFilters} />
      <main id="main-content" className="flex-1 overflow-auto">
        <div className="p-[24px] space-y-[16px]">
          <div className="flex items-center justify-between flex-wrap gap-[16px]">
            <h1 className="font-display text-[28px] font-semibold leading-[1.2]">
              {t('heading', 'Intakes')}
            </h1>
            <div className="flex items-center gap-[8px]">
              <ViewToggle view={view} onChange={setView} />
              <Button
                className="min-h-[44px]"
                onClick={() => navigate('/chat/new')}
              >
                {t('common:cta.newIntake')}
              </Button>
            </div>
          </div>
          {isLoading ? (
            <div className="space-y-[8px]">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : intakes.length === 0 ? (
            <EmptyState
              heading={t(`empty.heading.${theme}`, 'No intakes yet')}
              body={t(
                'empty.body',
                'Start a new intake to begin. The button above will walk you through it.'
              )}
              action={
                <Button
                  onClick={() => navigate('/chat/new')}
                  className="min-h-[44px]"
                >
                  {t('common:cta.newIntake')}
                </Button>
              }
            />
          ) : view === 'table' ? (
            intakes.length >= VIRTUAL_THRESHOLD ? (
              <IntakeVirtualList intakes={intakes} />
            ) : (
              <IntakeTable intakes={intakes} />
            )
          ) : (
            <IntakeCardGrid intakes={intakes} />
          )}
        </div>
      </main>
    </div>
  )
}
