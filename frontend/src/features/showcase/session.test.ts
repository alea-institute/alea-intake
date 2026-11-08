import { afterEach, it, expect, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/msw/server'
import { createSessionKeepalive, sendStory } from './session'
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); sessionStorage.clear() })
it('waits for a system response after ack when it arrives before the deadline',async()=>{
 let socket: {onopen?:()=>void;onmessage?:(e:{data:string})=>void;send:ReturnType<typeof vi.fn>;close:ReturnType<typeof vi.fn>}
 class Socket { onopen?:()=>void;onmessage?:(e:{data:string})=>void;send=vi.fn();close=vi.fn();constructor(){socket=this} }
 vi.stubGlobal('WebSocket',Socket)
 sessionStorage.setItem('showcase-token','guest');sessionStorage.setItem('showcase-key',JSON.stringify({key:'sk-fake-key',provider:'openai',model:'gpt-4.1-mini'}))
 let resolved=false
 const pending=sendStory(2,3,'My wages are missing.').then(()=>{resolved=true})
 socket!.onopen?.()
 expect(JSON.parse(socket!.send.mock.calls[0][0])).toEqual({type:'auth',token:'guest',llm_api_key:'sk-fake-key',llm_provider:'openai',llm_model:'gpt-4.1-mini'})
 socket!.onmessage?.({data:'{"type":"message_ack"}'})
 await Promise.resolve();expect(resolved).toBe(false)
 socket!.onmessage?.({data:'{"type":"system_message","content":"Saved"}'})
 await pending;expect(resolved).toBe(true)
 vi.unstubAllGlobals()
})

it.each(['connecting', 'awaiting reply'])('times out and closes a socket stuck %s', async phase => {
 vi.useFakeTimers()
 let socket: {onopen?:()=>void;send:ReturnType<typeof vi.fn>;close:ReturnType<typeof vi.fn>}
 class Socket { onopen?:()=>void;send=vi.fn();close=vi.fn();constructor(){socket=this} }
 vi.stubGlobal('WebSocket',Socket)
 const pending = sendStory(2,3,'Keep my story.')
 const rejected = expect(pending).rejects.toBeInstanceOf(TypeError)
 if (phase === 'awaiting reply') socket!.onopen?.()
 await vi.advanceTimersByTimeAsync(120000)
 await rejected
 expect(socket!.close).toHaveBeenCalledOnce()
})

it('aborts and closes the socket without a later timeout', async () => {
 vi.useFakeTimers()
 const close = vi.fn()
 class Socket { close=close }
 vi.stubGlobal('WebSocket',Socket)
 const controller = new AbortController()
 const pending = sendStory(2,3,'Keep my story.',controller.signal)
 const rejected = expect(pending).rejects.toMatchObject({name:'AbortError'})
 controller.abort()
 await rejected
 await vi.advanceTimersByTimeAsync(120000)
 expect(close).toHaveBeenCalledOnce()
 expect(vi.getTimerCount()).toBe(0)
})

it('throttles authenticated intake keepalive to once per minute, including failures', async () => {
 let calls = 0
 sessionStorage.setItem('showcase-token','guest')
 server.use(http.get('/api/v1/intake/1/messages', ({request}) => {
   expect(request.headers.get('Authorization')).toBe('Bearer guest')
   expect(new URL(request.url).searchParams.get('session_id')).toBe('2')
   expect(new URL(request.url).searchParams.get('limit')).toBe('1')
   calls++
   return calls === 1 ? HttpResponse.error() : HttpResponse.json([])
 }))
 const clock = vi.spyOn(Date, 'now').mockReturnValue(100000)
 const keepalive = createSessionKeepalive(1,2)
 await expect(keepalive()).rejects.toBeInstanceOf(TypeError)
 await keepalive(); expect(calls).toBe(1)
 clock.mockReturnValue(159999)
 await keepalive(); expect(calls).toBe(1)
 clock.mockReturnValue(160000)
 await Promise.all([keepalive(), keepalive()]); expect(calls).toBe(2)
 clock.mockRestore()
})

class DeliverySocket {
 static instances: DeliverySocket[] = []
 onopen?: () => void
 onmessage?: (e: {data: string}) => void
 onclose?: (e: {code: number}) => void
 onerror?: () => void
 send = vi.fn()
 close = vi.fn()
 constructor() { DeliverySocket.instances.push(this) }
 frame(message: unknown) { this.onmessage?.({data: JSON.stringify(message)}) }
}
function deliverySocket() {
 DeliverySocket.instances = []
 vi.stubGlobal('WebSocket', DeliverySocket)
}
it('resolves after ack even if the system response never arrives, and skips resending a delivered story', async () => {
 vi.useFakeTimers(); deliverySocket()
 const pending = sendStory(2,3,'Already stored story.')
 const socket = DeliverySocket.instances[0]
 socket.onopen?.()
 socket.frame({type:'message_ack'})
 const marker = Object.keys(sessionStorage).find(key => key.startsWith('showcase-story:2:'))
 expect(marker).toBeDefined()
 expect(marker).not.toContain('Already stored story.')
 expect(JSON.parse(sessionStorage.getItem(marker!)!)).toMatchObject({delivered:true})
 const completed = expect(pending).resolves.toBeUndefined()
 await vi.advanceTimersByTimeAsync(120000)
 await completed
 await sendStory(2,3,'Already stored story.')
 expect(DeliverySocket.instances).toHaveLength(1)
 expect(socket.close).toHaveBeenCalledOnce()
})
it('keeps the same client id across retries before ack, scoped to session and story', async () => {
 deliverySocket()
 const first = sendStory(2,3,'Retry me.')
 const a = DeliverySocket.instances[0]; a.onopen?.()
 const failed = expect(first).rejects.toBeInstanceOf(TypeError)
 a.onerror?.(); await failed
 const retry = sendStory(2,3,'Retry me.')
 const b = DeliverySocket.instances[1]; b.onopen?.()
 expect(JSON.parse(b.send.mock.calls[1][0]).client_id).toBe(JSON.parse(a.send.mock.calls[1][0]).client_id)
 b.frame({type:'message_ack'}); b.frame({type:'system_message'}); await retry
 for (const [session, text] of [[3,'Retry me.'], [2,'Changed story.']] as const) {
   const pending = sendStory(session,3,text)
   const socket = DeliverySocket.instances.at(-1)!
   socket.onopen?.()
   expect(JSON.parse(socket.send.mock.calls[1][0]).client_id).not.toBe(JSON.parse(a.send.mock.calls[1][0]).client_id)
   socket.frame({type:'message_ack'}); socket.frame({type:'system_message'}); await pending
 }
})
it('ignores malformed frames and requires ack even if a system response arrives', async () => {
 vi.useFakeTimers(); deliverySocket()
 const pending = sendStory(2,3,'Unacknowledged story.')
 const socket = DeliverySocket.instances[0]; socket.onopen?.()
 for (const data of ['invalid json', 'null', '[]']) expect(() => socket.onmessage?.({data})).not.toThrow()
 socket.frame({type:'message_ack',client_id:'another-story'})
 socket.frame({type:'system_message'})
 const failed = expect(pending).rejects.toBeInstanceOf(TypeError)
 await vi.advanceTimersByTimeAsync(120000); await failed
})
it('maps close code 4004 to an expired session', async () => {
 deliverySocket()
 const pending = sendStory(2,3,'Expired story.')
 const failed = expect(pending).rejects.toMatchObject({status:410})
 DeliverySocket.instances[0].onclose?.({code:4004})
 await failed
})
