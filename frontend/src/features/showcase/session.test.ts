import { it, expect, vi } from 'vitest'
import { sendStory } from './session'
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
