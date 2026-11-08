export const showcaseMode = import.meta.env.VITE_SHOWCASE_MODE === 'true'
export const defaultModels: Record<string, string> = {openai:'gpt-4.1-mini',anthropic:'claude-haiku-4-5',google:'gemini-2.5-flash'}
export const referenceModel = import.meta.env.VITE_REFERENCE_MODEL || defaultModels[import.meta.env.VITE_REFERENCE_PROVIDER || 'openai']
export const referenceProvider = import.meta.env.VITE_REFERENCE_PROVIDER || 'openai'
export const TERMINAL_ANALYSIS_STATUSES = ['completed', 'complete', 'converged', 'max_iterations'] as const
export interface VisitorKey { key: string; provider: string; model: string }
export function readKey(): VisitorKey {
  const raw = sessionStorage.getItem('showcase-key')
  return raw ? JSON.parse(raw) : { key: '', provider: referenceProvider, model: referenceModel }
}
export function keyHeaders(): Record<string, string> {
  const k = readKey()
  return { 'X-LLM-API-Key': k.key, 'X-LLM-Provider': k.provider, 'X-LLM-Model': k.model }
}
export function authFrame(token: string) {
  const k = readKey()
  return { type: 'auth', token, llm_api_key: k.key, llm_provider: k.provider, llm_model: k.model }
}
export class RequestError extends Error {
  constructor(public status: number) { super(String(status)) }
}
export async function request(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers)
  const token = sessionStorage.getItem('showcase-token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  for (const [k,v] of Object.entries(keyHeaders())) headers.set(k,v)
  const response = await fetch(path, { ...init, headers })
  if (!response.ok) throw new RequestError(response.status)
  return response
}
export async function json(path: string, body?: unknown, init: RequestInit = {}) {
  const res = await request(path, { ...init, ...(body === undefined ? {} : { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) }) })
  return res.json()
}
export function createSessionKeepalive(intakeId: number, sessionId: number) {
  let lastSent = -Infinity
  return async () => {
    if (Date.now() - lastSent < 60000) return
    lastSent = Date.now()
    await request(`/api/v1/intake/${intakeId}/messages?session_id=${sessionId}&limit=1`)
  }
}

export function sendStory(sessionId: number, partyId: number, story: string, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) { reject(signal.reason); return }
    const ws = new WebSocket(intakeSocketUrl(sessionId))
    let settled = false
    const finish = (error?: Error) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      signal?.removeEventListener('abort', abort)
      ws.onopen = ws.onmessage = ws.onerror = ws.onclose = null
      ws.close()
      if (error) reject(error)
      else resolve()
    }
    const abort = () => finish(signal?.reason ?? new DOMException('Aborted', 'AbortError'))
    const timer = setTimeout(() => finish(new TypeError('network')), 120000)
    signal?.addEventListener('abort', abort, {once:true})
    ws.onopen = () => { ws.send(JSON.stringify(authFrame(sessionStorage.getItem('showcase-token')!))); ws.send(JSON.stringify({type:'text_message', content: story, party_id: partyId, client_id: crypto.randomUUID()})) }
    ws.onmessage = e => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'system_message') finish()
      if (msg.type === 'error') finish(new RequestError(msg.status || 500))
    }
    ws.onerror = () => finish(new TypeError('network'))
    ws.onclose = e => finish(e.code === 4001 || e.code === 4003 ? new RequestError(401) : new TypeError('network'))
  })
}

export function intakeSocketUrl(sessionId: string | number): string {
  return `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws/intake/${sessionId}`
}
