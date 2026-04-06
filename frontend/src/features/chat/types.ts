export type Modality = 'text' | 'voice' | 'document'
export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting' | 'error'
export type MessageStatus = 'pending' | 'sent' | 'failed' | 'streaming' | 'done'
export type Sender = 'consumer' | 'system' | 'professional'

export interface Message {
  id: string
  clientId?: string
  sessionId: string
  sender: Sender
  modality: Modality
  content: string
  timestamp: string
  status: MessageStatus
  extractionStatus?: 'pending' | 'complete' | 'failed'
}

export interface AnalysisProgress {
  stage: number
  totalStages: number
  stageName: string
  iteration: number
  completeness: number
  nextStage?: string
}

export interface SafetyAlert {
  tier: 'critical' | 'elevated' | 'advisory'
  category: string
  message: string
  resources: Array<{ name: string; url?: string; phone?: string }>
  addressed?: boolean
}

// WebSocket events (server -> client)
export type WSEvent =
  | { type: 'message_ack'; client_id: string; id: string; timestamp: string }
  | { type: 'llm_stream'; message_id: string; token: string; done: boolean }
  | { type: 'analysis_progress'; data: AnalysisProgress }
  | { type: 'safety_alert'; tier: SafetyAlert['tier']; payload: SafetyAlert }
  | { type: 'fact_extracted'; count: number }
  | { type: 'error'; code: string; message: string }

// WebSocket commands (client -> server)
export type WSCommand =
  | { type: 'client_message'; client_id: string; modality: Modality; content: string }
  | { type: 'stream_cancel'; message_id: string }
  | { type: 'ping' }
