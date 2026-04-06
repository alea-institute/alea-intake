import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  useAutonomyConfig,
  useUpdateAutonomyConfig,
  useStages,
  usePresets,
} from '@/features/autonomy/hooks'
import type {
  AutonomyConfig,
  StageCheckpoint,
  TimeoutBehavior,
  SafetyBehavior,
} from '@/features/autonomy/types'

const STAGE_LABEL_KEYS: Record<string, string> = {
  issue_spot: 'autonomy.stages.issue_spot',
  explore: 'autonomy.stages.explore',
  research: 'autonomy.stages.research',
  fact_map: 'autonomy.stages.fact_map',
  gap_analyze: 'autonomy.stages.gap_analyze',
  question_gen: 'autonomy.stages.question_gen',
}

const STAGE_LABEL_DEFAULTS: Record<string, string> = {
  issue_spot: 'Issue Spotting',
  explore: 'Exploration',
  research: 'Legal Research',
  fact_map: 'Fact Mapping',
  gap_analyze: 'Gap Analysis',
  question_gen: 'Question Generation',
}

function buildPreviewText(config: AutonomyConfig): string {
  const allAuto = Object.values(config.stage_checkpoints).every((v) => v === 'auto')
  const allCheckpoint = Object.values(config.stage_checkpoints).every((v) => v === 'checkpoint')

  if (allAuto) {
    return 'In this configuration, the system runs fully autonomously. Consumers will see: [AI Assistant] on system messages.'
  }
  if (allCheckpoint) {
    return 'In this configuration, every stage requires professional review. When analysis pauses, consumers will see: [Analysis paused for review].'
  }
  const checkpointed = Object.entries(config.stage_checkpoints)
    .filter(([, v]) => v === 'checkpoint')
    .map(([k]) => STAGE_LABEL_DEFAULTS[k] ?? k)
  return `In this configuration, the following stages require review: ${checkpointed.join(', ')}. When analysis pauses, consumers will see: [Analysis paused for review].`
}

export function AutonomySettings() {
  const { t } = useTranslation('admin')
  const { data: serverConfig } = useAutonomyConfig()
  const { data: stages } = useStages()
  const { data: presets } = usePresets()
  const updateMutation = useUpdateAutonomyConfig()

  const [localConfig, setLocalConfig] = useState<AutonomyConfig | null>(null)

  useEffect(() => {
    if (serverConfig && !localConfig) {
      setLocalConfig(serverConfig)
    }
  }, [serverConfig, localConfig])

  const applyPreset = useCallback(
    (presetName: string) => {
      if (!presets?.[presetName]) return
      setLocalConfig({ ...presets[presetName] })
    },
    [presets],
  )

  const handleStageToggle = useCallback(
    (stage: string, checked: boolean) => {
      if (!localConfig) return
      const value: StageCheckpoint = checked ? 'checkpoint' : 'auto'
      setLocalConfig({
        ...localConfig,
        stage_checkpoints: { ...localConfig.stage_checkpoints, [stage]: value },
      })
    },
    [localConfig],
  )

  const handleSave = useCallback(() => {
    if (!localConfig) return
    updateMutation.mutate(localConfig, {
      onSuccess: () => toast.success(t('autonomy.saved', 'Configuration saved')),
      onError: () => toast.error(t('autonomy.saveError', 'Failed to save configuration')),
    })
  }, [localConfig, updateMutation, t])

  if (!localConfig || !stages) {
    return (
      <div className="space-y-md animate-pulse">
        <div className="h-8 w-48 bg-muted rounded" />
        <div className="h-4 w-64 bg-muted rounded" />
        <div className="h-4 w-56 bg-muted rounded" />
      </div>
    )
  }

  return (
    <div className="space-y-[24px] max-w-2xl">
      {/* Preset buttons */}
      <section>
        <h3 className="font-display text-[20px] mb-[8px]">
          {t('autonomy.presets.title', 'Mode Presets')}
        </h3>
        <div className="flex flex-wrap gap-[8px]">
          <Button
            type="button"
            variant="outline"
            onClick={() => applyPreset('chatbot')}
            className="min-h-[44px]"
          >
            {t('autonomy.presets.chatbot', 'Chatbot (Fully Autonomous)')}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => applyPreset('professional')}
            className="min-h-[44px]"
          >
            {t('autonomy.presets.professional', 'Professional (Full Oversight)')}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => applyPreset('agent')}
            className="min-h-[44px]"
          >
            {t('autonomy.presets.agent', 'Agent (Selective Checkpoints)')}
          </Button>
        </div>
      </section>

      {/* Per-stage toggles */}
      <section>
        <h3 className="font-display text-[20px] mb-[8px]">
          {t('autonomy.stages.title', 'Stage Checkpoints')}
        </h3>
        <div className="space-y-[12px]">
          {stages.map((stage) => {
            const isCheckpoint = localConfig.stage_checkpoints[stage] === 'checkpoint'
            const labelKey = STAGE_LABEL_KEYS[stage]
            const labelDefault = STAGE_LABEL_DEFAULTS[stage] ?? stage
            return (
              <div key={stage} className="flex items-center justify-between min-h-[44px]">
                <label htmlFor={`stage-${stage}`} className="font-body text-[16px]">
                  {labelKey ? t(labelKey, labelDefault) : labelDefault}
                </label>
                <Switch
                  id={`stage-${stage}`}
                  checked={isCheckpoint}
                  onCheckedChange={(checked) => handleStageToggle(stage, !!checked)}
                  aria-label={`${labelDefault} checkpoint toggle`}
                />
              </div>
            )
          })}
        </div>
      </section>

      {/* Timeout configuration */}
      <section>
        <h3 className="font-display text-[20px] mb-[8px]">
          {t('autonomy.timeout.title', 'Timeout Configuration')}
        </h3>
        <div className="space-y-[12px]">
          <div>
            <label htmlFor="timeout-duration" className="block font-body text-[14px] font-medium mb-[4px]">
              {t('autonomy.timeout.duration', 'Timeout Duration (seconds)')}
            </label>
            <Input
              id="timeout-duration"
              type="number"
              min="60"
              step="60"
              value={localConfig.timeout_seconds}
              onChange={(e) =>
                setLocalConfig({
                  ...localConfig,
                  timeout_seconds: Math.max(60, parseInt(e.target.value, 10) || 60),
                })
              }
              className="min-h-[44px] max-w-[200px]"
            />
          </div>
          <div>
            <label htmlFor="timeout-behavior" className="block font-body text-[14px] font-medium mb-[4px]">
              {t('autonomy.timeout.behavior', 'On Timeout')}
            </label>
            <Select
              value={localConfig.timeout_behavior}
              onValueChange={(v) =>
                setLocalConfig({ ...localConfig, timeout_behavior: v as TimeoutBehavior })
              }
            >
              <SelectTrigger id="timeout-behavior" className="min-h-[44px] max-w-[320px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto_proceed">
                  {t('autonomy.timeout.auto_proceed', 'Auto-proceed with audit note')}
                </SelectItem>
                <SelectItem value="queue_next">
                  {t('autonomy.timeout.queue_next', 'Queue for next available professional')}
                </SelectItem>
                <SelectItem value="pause_until">
                  {t('autonomy.timeout.pause_until', 'Pause until approved')}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </section>

      {/* Safety behavior */}
      <section>
        <h3 className="font-display text-[20px] mb-[8px]">
          {t('autonomy.safety.title', 'Safety Behavior')}
        </h3>
        <RadioGroup
          value={localConfig.safety_behavior}
          onValueChange={(v) =>
            setLocalConfig({ ...localConfig, safety_behavior: v as SafetyBehavior })
          }
          className="space-y-[8px]"
        >
          <div className="flex items-start gap-[8px]">
            <RadioGroupItem value="strict" id="safety-strict" className="mt-1" />
            <label htmlFor="safety-strict" className="font-body text-[16px]">
              <span className="font-medium">
                {t('autonomy.safety.strict', 'Strict (all critical + elevated mandatory)')}
              </span>
              <span className="block text-[14px] text-muted-foreground">
                All critical and elevated safety alerts require professional review before proceeding.
              </span>
            </label>
          </div>
          <div className="flex items-start gap-[8px]">
            <RadioGroupItem value="professional" id="safety-professional" className="mt-1" />
            <label htmlFor="safety-professional" className="font-body text-[16px]">
              <span className="font-medium">
                {t('autonomy.safety.professional', 'Professional (critical mandatory, elevated silenceable)')}
              </span>
              <span className="block text-[14px] text-muted-foreground">
                Critical alerts always pause. Elevated alerts can be silenced by the professional.
              </span>
            </label>
          </div>
        </RadioGroup>
      </section>

      {/* Notifications */}
      <section>
        <h3 className="font-display text-[20px] mb-[8px]">Notifications</h3>
        <div className="space-y-[12px]">
          <div className="flex items-center justify-between min-h-[44px]">
            <label htmlFor="notify-ws" className="font-body text-[16px]">
              WebSocket notifications
            </label>
            <Switch id="notify-ws" checked={localConfig.notify_websocket} disabled aria-label="WebSocket notifications" />
          </div>
          <div className="flex items-center justify-between min-h-[44px]">
            <label htmlFor="notify-email" className="font-body text-[16px]">
              Email notifications
            </label>
            <Switch
              id="notify-email"
              checked={localConfig.notify_email}
              onCheckedChange={(checked) =>
                setLocalConfig({ ...localConfig, notify_email: !!checked })
              }
              aria-label="Email notifications"
            />
          </div>
        </div>
      </section>

      {/* Mode preview */}
      <section>
        <h3 className="font-display text-[20px] mb-[8px]">
          {t('autonomy.preview.title', 'Consumer Experience Preview')}
        </h3>
        <div className="bg-muted/50 rounded-md p-[16px] font-body text-[14px] text-muted-foreground">
          {buildPreviewText(localConfig)}
        </div>
      </section>

      {/* Save */}
      <Button
        type="button"
        onClick={handleSave}
        disabled={updateMutation.isPending}
        className="min-h-[44px]"
      >
        {updateMutation.isPending
          ? t('autonomy.saving', 'Saving...')
          : t('autonomy.save', 'Save Configuration')}
      </Button>
    </div>
  )
}
