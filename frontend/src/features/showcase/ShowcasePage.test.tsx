import { Suspense } from 'react'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, screen, waitFor, cleanup, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/msw/server'
import { renderWithProviders } from '@/test/utils'
import { ShowcasePage } from './ShowcasePage'
import copy from '../../../public/locales/en/showcase.json'
import { wageTheftVisualization } from '@/test/fixtures/showcase'

const translations = vi.hoisted(() => ({
  i18n: { loadNamespaces: vi.fn().mockResolvedValue(undefined) },
  pending: null as Promise<void> | null,
  suspended: vi.fn(),
}))
vi.mock('react-i18next', () => ({ useTranslation: (namespace: string) => {
  if (namespace === 'chat' && sessionStorage.getItem('showcase-intake') && translations.pending) {
    translations.suspended()
    throw translations.pending
  }
  return { i18n: translations.i18n, t: (key: string, opts?: Record<string, unknown>) => {
  let value = (copy as Record<string, string>)[key] ?? String(opts?.defaultValue ?? key)
  for (const [k,v] of Object.entries(opts ?? {})) value = value.replace(`{{${k}}}`, String(v))
  return value
} }
} }))
let submittedStory = '', hangSocket = false, socketClosed = false, storySends = 0, closeCode = 0
class Socket {
  onopen?: () => void; onmessage?: (e: {data:string}) => void; onerror?: () => void; onclose?: (e: {code:number}) => void
  constructor() { queueMicrotask(() => this.onopen?.()) }
  send(raw: string) {
    const frame = JSON.parse(raw)
    if (frame.type !== 'text_message') return
    storySends++
    if (closeCode) { queueMicrotask(() => this.onclose?.({code:closeCode})); return }
    submittedStory = frame.content
    if (!hangSocket) queueMicrotask(() => {
      this.onmessage?.({data: JSON.stringify({type:'message_ack',client_id:frame.client_id})})
      this.onmessage?.({data:'{"type":"system_message","content":"Saved"}'})
    })
  }
  close() { socketClosed = true }
}
let analyses = 0, uploads = 0, ended = 0
beforeEach(() => {
  translations.pending = null; translations.suspended.mockClear(); translations.i18n.loadNamespaces.mockClear()
  sessionStorage.clear(); localStorage.clear(); analyses = uploads = ended = 0
  hangSocket = socketClosed = false; storySends = closeCode = 0
  vi.stubGlobal('WebSocket', Socket)
  server.use(
    http.get('/api/v1/auth/showcase-notice', () => HttpResponse.json({ consent_text: 'Allow AI processing', idle_ttl_seconds: 120 })),
    http.post('/api/v1/auth/guest', () => HttpResponse.json({access_token:'guest'})),
    http.post('/api/v1/consent/grant', () => HttpResponse.json({})),
    http.post('/api/v1/intake/', () => HttpResponse.json({id:1,session_id:2,party_id:3})),
    http.post('/api/v1/intake/1/document', () => { uploads++; return HttpResponse.json({}) }),
    http.post('/api/v1/analysis/1/analyze', () => { analyses++; return HttpResponse.json({run_id:4,status:'completed',is_reference_model:true}) }),
    http.get('/api/v1/analysis/1/results', () => HttpResponse.json({claims:[{id:1,claim_name:'Unpaid wages',folio_iri:'https://folio.openlegalstandard.org/wages'}],deadlines:[{event_text:'Wage demand',computed_date:'2026-12-01',computed:true,citation:'Minn. Stat.',citation_url:'https://www.revisor.mn.gov/',counting_method:'Calendar days',as_of_date:'2026-11-08'}]})),
    http.get('/api/v1/analysis/1/visualization', () => HttpResponse.json(wageTheftVisualization)),
    http.post('/api/v1/output/generate', () => HttpResponse.json({documents:[{id:5}]})),
    http.get('/api/v1/output/5', () => HttpResponse.json({markdown_content:'# Your memo'})),
    http.post('/api/v1/intake/1/end-session', () => { ended++; return HttpResponse.json({}) }),
  )
})
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })
async function ready() {
  renderWithProviders(<ShowcasePage />)
  await screen.findByText('Allow AI processing')
  fireEvent.click(screen.getByLabelText('Allow AI processing'))
}
function key() { fireEvent.change(screen.getByLabelText('API key'), {target:{value:'sk-test-showcase-key'}}) }
function story() { fireEvent.change(screen.getByLabelText('Your story'), {target:{value:'My employer withheld my wages in Minnesota.'}}) }
function expectLandmarkContainment() {
  const outside = Array.from(document.body.querySelectorAll('*')).filter(element =>
    !['SCRIPT', 'STYLE'].includes(element.tagName) &&
    Array.from(element.childNodes).some(node => node.nodeType === Node.TEXT_NODE && node.textContent?.trim()) &&
    !element.closest('main, header, nav, footer, [role="alertdialog"]')
  )
  expect(outside.map(element => element.textContent)).toEqual([])
  const banners = screen.getAllByRole('banner', {hidden:true}).filter(element => !element.closest('main'))
  expect(banners).toHaveLength(1)
  expect(within(banners[0]).getByRole('note', {hidden:true})).toHaveTextContent('A FOLIO demonstration. Not legal advice.')
}
describe('showcase', () => {
  it('completes analysis when a child namespace suspends after session creation', async () => {
    let notices = 0
    server.use(http.get('/api/v1/auth/showcase-notice', () => {
      notices++
      return HttpResponse.json({consent_text: 'Allow AI processing', idle_ttl_seconds: 120})
    }))
    let resolveNamespace!: () => void
    translations.pending = new Promise<void>(resolve => { resolveNamespace = resolve })
    const namespaceLoaded = translations.pending
    server.use(http.post('/api/v1/analysis/1/analyze', async () => {
      analyses++
      await namespaceLoaded
      return HttpResponse.json({run_id: 4, status: 'completed', is_reference_model: true})
    }))
    renderWithProviders(<Suspense fallback={<p>Loading application</p>}><ShowcasePage /></Suspense>)
    await screen.findByText('Allow AI processing')
    fireEvent.click(screen.getByLabelText('Allow AI processing'))
    key(); story(); fireEvent.click(screen.getByText('Analyze my story'))
    await waitFor(() => expect(translations.suspended).toHaveBeenCalled())
    expect(screen.queryByText('Loading application')).not.toBeInTheDocument()
    await act(async () => {
      translations.pending = null
      resolveNamespace()
    })
    await screen.findByRole('heading', {name: 'Unpaid wages'})
    expect(analyses).toBe(1)
    expect(screen.queryByText(/Analysis stopped/)).not.toBeInTheDocument()
    expect(notices).toBe(1)
    expect(translations.i18n.loadNamespaces).toHaveBeenCalledWith(['chat', 'showcase'])
  })
  it('contains the disclaimer note and every result view in landmarks', async () => {
    await ready()
    expectLandmarkContainment()
    key(); story(); fireEvent.click(screen.getByText('Analyze my story'))
    await screen.findByRole('heading', {name:'Unpaid wages'})
    for (const name of ['Your story', 'Graph', 'Matrix', 'Deadlines', 'Memo']) {
      fireEvent.click(screen.getByRole('button', {name}))
      expectLandmarkContainment()
    }
  })
  it('shows provider names and selects low-cost models', async () => {
    await ready()
    expect(screen.getByLabelText('Model')).toHaveValue('gpt-4.1-mini')
    for (const [id, label, model] of [
      ['anthropic', 'Anthropic', 'claude-haiku-4-5'],
      ['google', 'Google', 'gemini-2.5-flash'],
      ['openai', 'OpenAI', 'gpt-4.1-mini'],
    ]) {
      expect(screen.getByRole('option', {name:label})).toHaveValue(id)
      fireEvent.change(screen.getByLabelText('Provider'), {target:{value:id}})
      expect(screen.getByLabelText('Model')).toHaveValue(model)
    }
    key(); story(); fireEvent.click(screen.getByText('Analyze my story'))
    await waitFor(() => expect(analyses).toBe(1))
    expect(JSON.parse(sessionStorage.getItem('showcase-key')!)).toMatchObject({provider:'openai',model:'gpt-4.1-mini'})
  })
  it('preselects the backend reference model and uses it in the quality notice', async () => {
    server.use(http.get('/api/v1/auth/showcase-notice', () => HttpResponse.json({consent_text:'Allow AI processing',reference_model:'configured-reference'})))
    await ready()
    expect(screen.getByLabelText('Model')).toHaveValue('configured-reference')
    fireEvent.change(screen.getByLabelText('Model'),{target:{value:'custom-model'}})
    expect(screen.getByText('Quality is verified only on configured-reference, the reference model. You can still run this analysis.')).toBeInTheDocument()
  })
  it('starts the mobile graph as a readable table and keeps a graph toggle', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation(query => ({matches:query==='(max-width: 600px)',media:query,onchange:null,addListener:vi.fn(),removeListener:vi.fn(),addEventListener:vi.fn(),removeEventListener:vi.fn(),dispatchEvent:vi.fn()}))
    await ready(); key(); story(); fireEvent.click(screen.getByText('Analyze my story'))
    await screen.findByRole('heading', {name:'Unpaid wages'})
    fireEvent.click(screen.getByRole('button', {name:'Graph'}))
    expect(screen.getByRole('table')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('checkbox', {name:copy.table}))
    expect(screen.getByRole('img', {name:'Force-directed graph visualization of facts, claims, and elements'})).toBeInTheDocument()
    vi.restoreAllMocks()
  })
  it('prompts for a missing key without analyzing', async () => {
    await ready(); story(); fireEvent.click(screen.getByText('Analyze my story'))
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a valid API key'); expect(analyses).toBe(0)
  })
  it('runs a curated story through issues, concepts, deadlines and memo export', async () => {
    await ready(); key(); fireEvent.change(screen.getByLabelText('Try an example'), {target:{value:'wage-theft'}})
    fireEvent.click(screen.getByText('Analyze my story'))
    await screen.findByRole('heading', {name:'Unpaid wages'})
    expect(document.querySelector('.showcase-narrative')).toHaveTextContent('108 hours')
    expect(screen.queryByText(/Landlord has refused/)).not.toBeInTheDocument()
    expect(screen.getByRole('link', {name:'Unpaid wages'})).toHaveAttribute('href','https://folio.openlegalstandard.org/wages')
    fireEvent.click(screen.getByText('Deadlines')); expect(screen.getByText('2026-12-01')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Memo')); expect(await screen.findByText('Your memo')).toBeInTheDocument()
    expect(screen.getAllByText('Export memo').length).toBeGreaterThan(0)
  })
  it.each(['text','pdf'])('starts analysis from %s', async mode => {
    await ready(); key()
    if(mode==='text') story()
    else fireEvent.change(screen.getByLabelText('Upload a PDF'), {target:{files:[new File(['pdf'], 'story.pdf',{type:'application/pdf'})]}})
    fireEvent.click(screen.getByText('Analyze my story')); await waitFor(() => expect(analyses).toBe(1))
    expect(uploads).toBe(mode==='pdf'?1:0)
  })
  it('keeps the key in tab storage through remount, never local storage', async () => {
    await ready(); key(); expect(localStorage.length).toBe(0)
    expect(sessionStorage.getItem('showcase-key')).toContain('sk-test-showcase-key')
    cleanup(); renderWithProviders(<ShowcasePage />)
    expect(screen.getByLabelText('API key')).toHaveValue('sk-test-showcase-key')
  })
  it.each([[401,'The provider rejected your key'],[429,'The provider or showcase reached a limit'],[500,'Analysis stopped']])('keeps the story for retry after %s', async (status, message) => {
    server.use(http.post('/api/v1/analysis/1/analyze', () => new HttpResponse(null,{status: Number(status)})))
    await ready(); key(); story(); fireEvent.click(screen.getByText('Analyze my story'))
    expect(await screen.findByRole('alert')).toHaveTextContent(String(message))
    expect(screen.getByLabelText('Your story')).toHaveValue('My employer withheld my wages in Minnesota.')
    expect(screen.getByText('Retry analysis')).toBeInTheDocument()
  })
  it('shows the reference model notice and still analyzes another model', async () => {
    await ready(); key(); story(); fireEvent.change(screen.getByLabelText('Model'),{target:{value:'another-model'}})
    expect(screen.getByText('Quality is verified only on gpt-4.1-mini, the reference model. You can still run this analysis.')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Analyze my story')); await waitFor(()=>expect(analyses).toBe(1))
  })
  it('offers retry after a network drop and completes without losing the story', async () => {
    server.use(http.post('/api/v1/analysis/1/analyze',()=>HttpResponse.error()))
    await ready(); key(); story(); fireEvent.click(screen.getByText('Analyze my story'))
    expect(await screen.findByRole('alert')).toHaveTextContent('The connection dropped')
    server.use(http.post('/api/v1/analysis/1/analyze',()=>HttpResponse.json({run_id:4,status:'completed'})))
    fireEvent.click(screen.getByText('Retry analysis')); await screen.findByRole('heading',{name:'Unpaid wages'})
    expect(screen.getByLabelText('Your story')).toHaveValue('My employer withheld my wages in Minnesota.')
    expect(storySends).toBe(1)
  })
  it.each(['/','/login','/admin','/oauth/finish','/intake/1/output'])('keeps the demonstration notice on %s', route => {
    renderWithProviders(<ShowcasePage />,{route})
    expect(screen.getByText('A FOLIO demonstration. Not legal advice.')).toBeInTheDocument()
    expect(screen.queryByText('Sign in')).not.toBeInTheDocument()
    expectLandmarkContainment()
  })
  it('submits a changed state and refreshes the returned deadlines', async () => {
    server.use(http.get('/api/v1/analysis/1/results',()=>HttpResponse.json({claims:[{id:1,claim_name:'Unpaid wages'}],deadlines:[{event_text:'File claim',computed:true,computed_date:submittedStory.includes('State confirmed by visitor: Minnesota.')?'2027-03-01':'2027-02-01'}]})))
    await ready(); key(); story();fireEvent.change(screen.getByLabelText('State'),{target:{value:'Wisconsin'}})
    fireEvent.click(screen.getByText('Analyze my story'));await screen.findByRole('heading',{name:'Unpaid wages'})
    fireEvent.click(screen.getByText('Deadlines'));expect(screen.getByText('2027-02-01')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('State'),{target:{value:'Minnesota'}})
    fireEvent.click(screen.getByText('Confirm state and update analysis'));await screen.findByRole('heading',{name:'Unpaid wages'})
    fireEvent.click(screen.getByText('Deadlines'));expect(screen.getByText('2027-03-01')).toBeInTheDocument()
    expect(submittedStory).toContain('State confirmed by visitor: Minnesota.')
  })
  it('ends and erases only after confirmation', async () => {
    await ready(); key(); story(); fireEvent.click(screen.getByText('Analyze my story')); await screen.findByText('Unpaid wages',{selector:'h3'})
    fireEvent.click(screen.getByText('End session and erase')); expect(ended).toBe(0)
    expectLandmarkContainment()
    fireEvent.click(screen.getByText('Erase this session')); await waitFor(() => expect(ended).toBe(1))
    expect(screen.getByLabelText('Your story')).toHaveValue(''); expect(sessionStorage.getItem('showcase-key')).toBeNull()
    expectLandmarkContainment()
  })
  it.each([401, 404, 500, 'network'])('wipes local data and releases a busy analysis when erase returns %s', async status => {
    server.use(http.post('/api/v1/intake/1/end-session', () => {
      ended++
      return status === 'network' ? HttpResponse.error() : new HttpResponse(null, {status: Number(status)})
    }))
    hangSocket = true
    const {queryClient} = renderWithProviders(<ShowcasePage />)
    await screen.findByText('Allow AI processing')
    fireEvent.click(screen.getByLabelText('Allow AI processing')); key(); story()
    sessionStorage.setItem('showcase-story', 'stored visitor story')
    fireEvent.click(screen.getByText('Analyze my story'))
    await screen.findByText('End session and erase')
    expect(screen.getByRole('button', {name: copy.busy})).toBeDisabled()
    fireEvent.click(screen.getByText('End session and erase'))
    fireEvent.click(screen.getByText('Erase this session'))
    await waitFor(() => expect(sessionStorage.length).toBe(0))
    expect(screen.getByLabelText('API key')).toHaveValue('')
    expect(screen.getByLabelText('Your story')).toHaveValue('')
    expect(screen.getByLabelText('Allow AI processing')).not.toBeChecked()
    expect(screen.getByRole('button', {name: 'Analyze my story'})).toBeEnabled()
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0)
    expect(socketClosed).toBe(true)
    if (status === 401 || status === 404) expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    else expect(screen.getByRole('alert')).toHaveTextContent('Local data was erased')
    vi.useFakeTimers()
    await act(async () => { vi.advanceTimersByTime(121000) })
    expect(ended).toBe(1)
  })
  it('wipes locally and shows the start screen before a hung server erase times out', async () => {
    sessionStorage.setItem('showcase-token','captured-guest')
    sessionStorage.setItem('showcase-intake',JSON.stringify({id:1,session_id:2,party_id:3}))
    const {queryClient} = renderWithProviders(<ShowcasePage />)
    await screen.findByText('Allow AI processing')
    key(); story()
    sessionStorage.setItem('showcase-story','private story')
    sessionStorage.setItem('showcase-story:2:hash',JSON.stringify({delivered:true}))
    queryClient.setQueryData(['private-data'], {story:'private story'})
    const fetch = vi.fn((_path: string, _init?: RequestInit) => new Promise<Response>(() => {}))
    vi.stubGlobal('fetch',fetch)
    fireEvent.click(screen.getByText('End session and erase'))
    vi.useFakeTimers()
    fireEvent.click(screen.getByText('Erase this session'))
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(sessionStorage.length).toBe(0)
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0)
    expect(screen.getByLabelText('API key')).toHaveValue('')
    expect(screen.getByLabelText('Your story')).toHaveValue('')
    expect(screen.getByRole('button',{name:'Analyze my story'})).toBeEnabled()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/v1/intake/1/end-session',expect.objectContaining({
      method:'POST', headers:expect.objectContaining({Authorization:'Bearer captured-guest'}),
    }))
    const signal = fetch.mock.calls[0][1]!.signal as AbortSignal
    await act(async () => { await vi.advanceTimersByTimeAsync(9999) })
    expect(signal.aborted).toBe(true)
    expect(screen.getByRole('alert')).toHaveTextContent('Local data was erased')
    expect(screen.getByRole('button',{name:'Analyze my story'})).toBeEnabled()
  })
  it('allows another local erase while a previous server erase is still pending', async () => {
    sessionStorage.setItem('showcase-token','guest')
    sessionStorage.setItem('showcase-intake',JSON.stringify({id:1,session_id:2,party_id:3}))
    await ready()
    const originalFetch = globalThis.fetch
    let finishFirst!: (response: Response) => void
    let eraseRequests = 0
    vi.stubGlobal('fetch',vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith('/end-session') && ++eraseRequests === 1) {
        return new Promise<Response>(resolve => { finishFirst = resolve })
      }
      return originalFetch(input, init)
    }))
    fireEvent.click(screen.getByText('End session and erase'))
    fireEvent.click(screen.getByText('Erase this session'))
    key(); story()
    fireEvent.click(screen.getByLabelText('Allow AI processing'))
    fireEvent.click(screen.getByText('Analyze my story'))
    await screen.findByRole('heading',{name:'Unpaid wages'})
    fireEvent.click(screen.getByText('End session and erase'))
    fireEvent.click(screen.getByText('Erase this session'))
    expect(sessionStorage.length).toBe(0)
    expect(screen.getByLabelText('Your story')).toHaveValue('')
    expect(eraseRequests).toBe(2)
    await act(async () => { finishFirst(new Response(null,{status:500})) })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
  it('stops polling and renders results at the iteration limit', async () => {
    let polls = 0
    server.use(
      http.post('/api/v1/analysis/1/analyze', () => HttpResponse.json({run_id:4,status:'running'})),
      http.get('/api/v1/analysis/1/status', () => { polls++; return HttpResponse.json({run_id:4,status:'max_iterations'}) }),
    )
    await ready(); key(); story(); fireEvent.click(screen.getByText('Analyze my story'))
    await screen.findByRole('heading', {name:'Unpaid wages'}, {timeout:4000})
    expect(screen.getByText('Analysis stopped at its iteration limit. The available results are shown below.')).toBeInTheDocument()
    expect(screen.getByRole('button', {name: 'Analyze my story'})).toBeEnabled()
    vi.useFakeTimers()
    await act(async () => { vi.advanceTimersByTime(10000) })
    expect(polls).toBe(1)
  })
  it('shows the expired screen and wipes local data on socket close 4004', async () => {
    closeCode = 4004
    await ready(); key(); story(); fireEvent.click(screen.getByText('Analyze my story'))
    await screen.findByText('Your session expired. The session data was erased.')
    expect(sessionStorage.length).toBe(0)
    expect(analyses).toBe(0)
    fireEvent.click(screen.getByText('Start a fresh session'))
    expect(screen.getByLabelText('Your story')).toHaveValue('')
  })
  it('offers retry after a socket timeout without losing the story', async () => {
    hangSocket = true
    const realSetTimeout = globalThis.setTimeout
    const timer = vi.spyOn(globalThis, 'setTimeout').mockImplementation(((callback, delay, ...args) => realSetTimeout(callback, delay === 120000 ? 50 : delay, ...args)) as typeof setTimeout)
    await ready(); key(); story(); fireEvent.click(screen.getByText('Analyze my story'))
    expect(await screen.findByRole('alert')).toHaveTextContent('The connection dropped')
    timer.mockRestore()
    expect(screen.getByLabelText('Your story')).toHaveValue('My employer withheld my wages in Minnesota.')
    expect(socketClosed).toBe(true)
    hangSocket = false
    fireEvent.click(screen.getByText('Retry analysis'))
    await screen.findByRole('heading', {name:'Unpaid wages'})
  })
  it('expires locally after an idle erase failure without retrying every second', async () => {
    sessionStorage.setItem('showcase-token','guest')
    sessionStorage.setItem('showcase-intake',JSON.stringify({id:1,session_id:2,party_id:3}))
    server.use(http.post('/api/v1/intake/1/end-session', () => { ended++; return new HttpResponse(null,{status:500}) }))
    await ready(); key()
    vi.useFakeTimers(); story()
    await act(async () => { vi.advanceTimersByTime(121000) })
    vi.useRealTimers()
    await screen.findByText('Your session expired. The session data was erased.')
    expect(screen.getByRole('alert')).toHaveTextContent('Local data was erased')
    expect(sessionStorage.length).toBe(0)
    vi.useFakeTimers()
    await act(async () => { vi.advanceTimersByTime(10000) })
    expect(ended).toBe(1)
    fireEvent.click(screen.getByText('Start a fresh session'))
    expect(screen.getByRole('button', {name:'Analyze my story'})).toBeEnabled()
  })
  it('keeps an existing session alive on pointer and keyboard activity across renders', async () => {
    sessionStorage.setItem('showcase-token','guest')
    sessionStorage.setItem('showcase-intake',JSON.stringify({id:1,session_id:2,party_id:3}))
    let calls = 0
    server.use(http.get('/api/v1/intake/1/messages', () => { calls++; return HttpResponse.json([]) }))
    await ready()
    const now = Date.now()
    const clock = vi.spyOn(Date,'now').mockReturnValue(now)
    fireEvent.pointerDown(window)
    await waitFor(() => expect(calls).toBe(1))
    key(); fireEvent.keyDown(window,{key:'a'}); fireEvent.pointerDown(window)
    await act(async () => {})
    expect(calls).toBe(1)
    clock.mockReturnValue(now+60000)
    fireEvent.keyDown(window,{key:'b'})
    await waitFor(() => expect(calls).toBe(2))
    clock.mockRestore()
  })
  it('warns before expiry and replaces the story with an erased screen', async () => {
    await ready(); vi.useFakeTimers(); story(); act(() => { vi.advanceTimersByTime(61000) })
    expect(screen.getByText('This session will expire soon. Export your memo or keep the session.')).toBeInTheDocument()
    expectLandmarkContainment()
    await act(async () => { vi.advanceTimersByTime(60000) })
    expect(screen.getByText('Your session expired. The session data was erased.')).toBeInTheDocument()
    expectLandmarkContainment()
  })
})
