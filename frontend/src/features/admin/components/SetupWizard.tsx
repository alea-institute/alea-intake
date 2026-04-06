import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'

const STEPS = [
  'profile',
  'deployment',
  'protocols',
  'profiles',
  'research',
  'kb',
] as const
type Step = (typeof STEPS)[number]

export function SetupWizard({ onFinish }: { onFinish: () => void }) {
  const { t } = useTranslation('admin')
  const [stepIdx, setStepIdx] = useState(0)
  const step: Step = STEPS[stepIdx]
  const pct = Math.round(((stepIdx + 1) / STEPS.length) * 100)

  return (
    <div className="max-w-xl mx-auto p-[24px] space-y-[24px]">
      <Progress value={pct} aria-valuenow={pct} />
      <p className="font-body text-[14px] text-muted-foreground">
        {t('wizard.stepLabel', 'Step {{n}} of {{total}}', {
          n: stepIdx + 1,
          total: STEPS.length,
        })}
      </p>
      <h2 className="font-display text-[28px] font-semibold leading-[1.2]">
        {t(`wizard.steps.${step}.title`, step)}
      </h2>
      <p className="font-body text-[16px] leading-[1.5]">
        {t(`wizard.steps.${step}.body`, 'Configure this section.')}
      </p>
      <div className="flex justify-between">
        <Button
          variant="outline"
          disabled={stepIdx === 0}
          onClick={() => setStepIdx((i) => i - 1)}
          className="min-h-[44px]"
        >
          {t('wizard.back', 'Back')}
        </Button>
        {stepIdx < STEPS.length - 1 ? (
          <Button
            onClick={() => setStepIdx((i) => i + 1)}
            className="min-h-[44px]"
          >
            {t('wizard.next', 'Next')}
          </Button>
        ) : (
          <Button onClick={onFinish} className="min-h-[44px]">
            {t('wizard.finish', 'Finish setup')}
          </Button>
        )}
      </div>
    </div>
  )
}
