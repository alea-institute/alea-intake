import type { SafetyAlert } from '@/features/chat/types'
// Safety alerts arrive as WebSocket events; there is no REST safety endpoint.
export async function fetchSafetyAlerts(_sessionId: string): Promise<SafetyAlert[]> {
  return []
}
