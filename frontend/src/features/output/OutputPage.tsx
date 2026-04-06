import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchOutput } from './api'
import { ProfileTabs } from './components/ProfileTabs'
import { ExportMenu } from './components/ExportMenu'
import { EmptyState } from '@/shared/components/EmptyState'

export function OutputPage() {
  const { id = '' } = useParams()
  const { t } = useTranslation('output')
  const { data, isLoading } = useQuery({
    queryKey: ['output', id],
    queryFn: () => fetchOutput(id),
    enabled: !!id,
  })

  return (
    <main id="main-content" className="flex-1 overflow-auto p-[24px]">
      <div className="max-w-3xl mx-auto space-y-[24px]">
        <div className="flex items-center justify-between flex-wrap gap-[16px]">
          <h1 className="font-display text-[28px] font-semibold leading-[1.2]">
            {t('heading', 'Output')}
          </h1>
          {data?.profiles && data.profiles.length > 0 && (
            <ExportMenu outputId={id} />
          )}
        </div>
        {isLoading ? (
          <div className="space-y-[8px]">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
          </div>
        ) : !data || data.profiles.length === 0 ? (
          <EmptyState
            heading={t('empty.heading', 'No output yet')}
            body={t(
              'empty.body',
              'Complete an intake conversation to generate output.'
            )}
          />
        ) : (
          <ProfileTabs profiles={data.profiles} />
        )}
      </div>
    </main>
  )
}
