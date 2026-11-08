import { afterEach, it, expect, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/msw/server'
import { createSessionKeepalive, sendStory } from './session'
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); sessionStorage.clear() })
it('waits for the committed system response before starting analysis',async()=>{
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
