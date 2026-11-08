import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

export type ShowcasePhase = 'story' | 'analysis' | 'memo'
export interface ShowcaseProgressState {
  phase: ShowcasePhase
  /** Raw backend stage key from `/analysis/{id}/status` (`latest_stage`); never rendered directly. */
  stage?: string | null
  /** Backend `progress_pct` (iterations finished out of the maximum). */
  pct?: number | null
  /** `Date.now()` when the visitor started this analysis. */
  startedAt: number
}

/** Backend analysis stage keys (orchestrator STAGES, the router's `question`/`converge`, and deadline detection) to showcase copy keys. */
export const STAGE_LABEL_KEYS: Record<string, string> = {
  issue_spot: 'stageIssueSpot',
  explore: 'stageExplore',
  research: 'stageResearch',
  fact_map: 'stageFactMap',
  gap_analyze: 'stageGapAnalyze',
  question_gen: 'stageQuestionGen',
  question: 'stageQuestionGen',
  deadline_detect: 'stageDeadlineDetect',
  converge: 'stageConverge',
}

/** The visitor-facing copy key for a backend stage; unknown or missing keys fall back to the generic label, never the raw key. */
export function stageLabelKey(stage?: string | null): string {
  return (stage && Object.prototype.hasOwnProperty.call(STAGE_LABEL_KEYS, stage)) ? STAGE_LABEL_KEYS[stage] : 'stageAnalyzing'
}

const TOTAL_STAGES = 3
const stageNumber: Record<ShowcasePhase, number> = { story: 1, analysis: 2, memo: 3 }

function secondsSince(startedAt: number) { return Math.max(0, Math.floor((Date.now() - startedAt) / 1000)) }

export function ShowcaseProgress({ progress }: { progress: ShowcaseProgressState }) {
  const { t } = useTranslation('showcase')
  // The panel title reuses the chat progress copy, already translated in every locale.
  const { t: tChat } = useTranslation('chat')
  const [elapsed, setElapsed] = useState(() => secondsSince(progress.startedAt))
  useEffect(() => {
    setElapsed(secondsSince(progress.startedAt))
    const timer = window.setInterval(() => setElapsed(secondsSince(progress.startedAt)), 1000)
    return () => clearInterval(timer)
  }, [progress.startedAt])

  const name = progress.phase === 'story' ? t('stageStory') : progress.phase === 'memo' ? t('stageMemo') : t(stageLabelKey(progress.stage))
  // Show a percentage only while analysis reports real partial progress; otherwise the bar sweeps indeterminately.
  const pct = progress.phase === 'analysis' && typeof progress.pct === 'number' && progress.pct > 0 && progress.pct < 100 ? Math.round(progress.pct) : undefined
  const stageText = t('progressStage', { n: stageNumber[progress.phase], total: TOTAL_STAGES, name })

  return <section className="showcase-progress" aria-labelledby="showcase-progress-title">
    <h2 id="showcase-progress-title">{tChat('progress.title')}</h2>
    <div className="showcase-progress-line">
      {/* Only the stage line is live, so screen readers hear stage changes, not the per-second clock. */}
      <p role="status" className="showcase-progress-stage">{stageText}</p>
      <p className="showcase-progress-elapsed" data-testid="showcase-elapsed">{t('elapsed', { seconds: elapsed })}</p>
    </div>
    <div
      className="showcase-progress-bar"
      role="progressbar"
      aria-label={stageText}
      aria-valuemin={pct === undefined ? undefined : 0}
      aria-valuemax={pct === undefined ? undefined : 100}
      aria-valuenow={pct}
      data-indeterminate={pct === undefined ? '' : undefined}
    ><span style={pct === undefined ? undefined : { width: `${pct}%` }} /></div>
    {pct !== undefined && <p className="showcase-progress-pct">{t('percentComplete', { pct })}</p>}
  </section>
}
