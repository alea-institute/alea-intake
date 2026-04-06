import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { AdminTabs } from './components/AdminTabs'
import { SetupWizard } from './components/SetupWizard'

export function AdminRouter() {
  const { t } = useTranslation('admin')
  const [mode, setMode] = useState<'tabs' | 'wizard'>('tabs')

  return (
    <main id="main-content" className="flex-1 overflow-auto p-[24px]">
      <div className="flex items-center justify-between mb-[24px] flex-wrap gap-[16px]">
        <h1 className="font-display text-[28px] font-semibold leading-[1.2]">
          {t('heading', 'Admin')}
        </h1>
        <Button
          variant="outline"
          onClick={() => setMode(mode === 'tabs' ? 'wizard' : 'tabs')}
          className="min-h-[44px]"
        >
          {mode === 'tabs'
            ? t('switchToWizard', 'Setup wizard')
            : t('switchToTabs', 'Tabbed view')}
        </Button>
      </div>
      {mode === 'tabs' ? (
        <AdminTabs />
      ) : (
        <SetupWizard onFinish={() => setMode('tabs')} />
      )}
    </main>
  )
}
