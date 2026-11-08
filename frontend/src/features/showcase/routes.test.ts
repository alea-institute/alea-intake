import { it, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/msw/server'
import { fetchIntakes } from '@/features/dashboard/api'
import { fetchOutput } from '@/features/output/api'
it('adapts the mounted intake list and output document routes',async()=>{
 server.use(http.get('/api/v1/intake/',()=>HttpResponse.json([{id:7,status:'new',created_at:'2026-11-08'}])),http.get('/api/v1/output/intake/7',()=>HttpResponse.json([{id:9,profile_type:'consumer',created_at:'2026-11-08'}])),http.get('/api/v1/output/9',()=>HttpResponse.json({id:9,profile_type:'consumer',markdown_content:'# Memo',created_at:'2026-11-08'})))
 expect((await fetchIntakes({})).items[0].id).toBe('7')
 expect((await fetchOutput('7')).profiles[0].content).toBe('# Memo')
})
