export const showcaseMode = import.meta.env.VITE_SHOWCASE_MODE === 'true'
export const defaultModels: Record<string, string> = {openai:'gpt-4.1-mini',anthropic:'claude-haiku-4-5',google:'gemini-2.5-flash'}
export const referenceModel = import.meta.env.VITE_REFERENCE_MODEL || defaultModels[import.meta.env.VITE_REFERENCE_PROVIDER || 'openai']
export const referenceProvider = import.meta.env.VITE_REFERENCE_PROVIDER || 'openai'
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
export async function json(path: string, body?: unknown) {
  const res = await request(path, body === undefined ? {} : { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) })
  return res.json()
}
export function sendStory(sessionId: number, partyId: number, story: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/ws/intake/${sessionId}`)
    let saved = false
    ws.onopen = () => { ws.send(JSON.stringify(authFrame(sessionStorage.getItem('showcase-token')!))); ws.send(JSON.stringify({type:'text_message', content: story, party_id: partyId, client_id: crypto.randomUUID()})) }
    ws.onmessage = e => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'system_message') { saved = true; resolve(); ws.close() }
      if (msg.type === 'error') { reject(new RequestError(msg.status || 500)); ws.close() }
    }
    ws.onerror = () => reject(new TypeError('network'))
    ws.onclose = e => { if (!saved) reject(e.code === 4001 || e.code === 4003 ? new RequestError(401) : new TypeError('network')) }
  })
}
