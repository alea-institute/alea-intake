export type StageCheckpoint = 'auto' | 'checkpoint'

export type TimeoutBehavior = 'auto_proceed' | 'queue_next' | 'pause_until'

export type SafetyBehavior = 'strict' | 'professional'

export interface AutonomyConfig {
  stage_checkpoints: Record<string, StageCheckpoint>
  timeout_seconds: number
  timeout_behavior: TimeoutBehavior
  safety_behavior: SafetyBehavior
  notify_websocket: boolean
  notify_email: boolean
  labels: Record<string, string>
}

export interface ApprovalRequest {
  id: number
  run_id: number
  iteration_id: number
  stage_name: string
  status: string
  safety_triggered: boolean
  is_rerun: boolean
  rerun_attempt: number
  guidance_text: string | null
  stage_output_json: Record<string, unknown>
  created_at: string
  resolved_at: string | null
}

export interface ApprovalAction {
  decision: 'approve' | 'reject' | 'edit'
  guidance_text?: string
  edits?: Record<string, unknown>
  actor_id?: string
}

export type AutonomyPresets = Record<string, AutonomyConfig>
