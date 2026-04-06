import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { approveStage, rejectStage, editStage } from '@/features/autonomy/api'
import type { ApprovalRequest } from '@/features/autonomy/types'

const STAGE_LABELS: Record<string, string> = {
  issue_spot: 'Issue Spotting',
  explore: 'Exploration',
  research: 'Legal Research',
  fact_map: 'Fact Mapping',
  gap_analyze: 'Gap Analysis',
  question_gen: 'Question Generation',
}

type ActionMode = 'idle' | 'reject' | 'edit'

interface Props {
  request: ApprovalRequest
  onAction: () => void
}

export function ApprovalCard({ request, onAction }: Props) {
  const { t } = useTranslation('chat')
  const [mode, setMode] = useState<ActionMode>('idle')
  const [guidanceText, setGuidanceText] = useState('')
  const [editJson, setEditJson] = useState(
    JSON.stringify(request.stage_output_json, null, 2),
  )
  const [loading, setLoading] = useState(false)

  const stageLabel = STAGE_LABELS[request.stage_name] ?? request.stage_name

  const handleApprove = useCallback(async () => {
    setLoading(true)
    try {
      await approveStage(request.id)
      onAction()
    } finally {
      setLoading(false)
    }
  }, [request.id, onAction])

  const handleReject = useCallback(async () => {
    setLoading(true)
    try {
      await rejectStage(request.id, guidanceText)
      onAction()
    } finally {
      setLoading(false)
    }
  }, [request.id, guidanceText, onAction])

  const handleEdit = useCallback(async () => {
    setLoading(true)
    try {
      const parsed = JSON.parse(editJson) as Record<string, unknown>
      await editStage(request.id, parsed)
      onAction()
    } catch {
      // JSON parse error or API error
    } finally {
      setLoading(false)
    }
  }, [request.id, editJson, onAction])

  return (
    <Card className="border-border shadow-sm">
      <CardHeader className="pb-[8px]">
        <div className="flex items-center gap-[8px]">
          <CardTitle className="font-display text-[20px]">
            {t('approval.title', 'Stage Review')}
          </CardTitle>
          {request.safety_triggered && (
            <Badge variant="destructive">{t('approval.safety_badge', 'Safety Alert')}</Badge>
          )}
        </div>
        <p className="font-body text-[16px] text-muted-foreground">{stageLabel}</p>
      </CardHeader>
      <CardContent className="space-y-[12px]">
        {/* Stage output preview */}
        <div className="bg-muted/50 rounded-md p-[12px] font-body text-[14px] max-h-[200px] overflow-auto">
          <pre className="whitespace-pre-wrap">
            {JSON.stringify(request.stage_output_json, null, 2)}
          </pre>
        </div>

        {/* Action buttons (idle mode) */}
        {mode === 'idle' && (
          <div className="flex flex-wrap gap-[8px]">
            <Button
              onClick={handleApprove}
              disabled={loading}
              className="min-h-[44px]"
            >
              {t('approval.approve', 'Approve')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => setMode('reject')}
              disabled={loading}
              className="min-h-[44px]"
            >
              {t('approval.reject', 'Reject')}
            </Button>
            <Button
              variant="secondary"
              onClick={() => setMode('edit')}
              disabled={loading}
              className="min-h-[44px]"
            >
              {t('approval.edit', 'Edit Output')}
            </Button>
          </div>
        )}

        {/* Reject flow */}
        {mode === 'reject' && (
          <div className="space-y-[8px]">
            <Textarea
              placeholder={t(
                'approval.guidance_placeholder',
                'Provide guidance for re-running this stage...',
              )}
              value={guidanceText}
              onChange={(e) => setGuidanceText(e.target.value)}
              className="min-h-[80px]"
            />
            <div className="flex gap-[8px]">
              <Button
                variant="destructive"
                onClick={handleReject}
                disabled={loading}
                className="min-h-[44px]"
              >
                {t('approval.submit_rejection', 'Submit Rejection')}
              </Button>
              <Button
                variant="ghost"
                onClick={() => setMode('idle')}
                disabled={loading}
                className="min-h-[44px]"
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Edit flow */}
        {mode === 'edit' && (
          <div className="space-y-[8px]">
            <Textarea
              value={editJson}
              onChange={(e) => setEditJson(e.target.value)}
              className="min-h-[120px] font-mono text-[14px]"
            />
            <div className="flex gap-[8px]">
              <Button
                onClick={handleEdit}
                disabled={loading}
                className="min-h-[44px]"
              >
                {t('approval.save_edits', 'Save Edits')}
              </Button>
              <Button
                variant="ghost"
                onClick={() => setMode('idle')}
                disabled={loading}
                className="min-h-[44px]"
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
