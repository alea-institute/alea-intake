import { AlertDialog, AlertDialogContent, AlertDialogTitle, AlertDialogDescription, AlertDialogAction, AlertDialogCancel } from '@/components/ui/alert-dialog'
import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { AnalysisProgressPanel } from '@/features/chat/components/AnalysisProgressPanel'
import { ThemeProvider } from '@/shared/components/ThemeProvider'
import { loadThemeFonts } from '@/shared/i18n/themes'
import type { VisualizationData } from '@/features/visualization/types'
import { Results, type ResultsData } from './Results'
import { pendingEraseStorageKey, usePendingErases } from './usePendingErases'
import { createSessionKeepalive, defaultModels, isStoryDelivered, json, readKey, referenceModel, request, RequestError, sendStory, TERMINAL_ANALYSIS_STATUSES } from './session'
import scenarios from './scenarios.json'
import './showcase.css'

const providers = {openai:'OpenAI',anthropic:'Anthropic',google:'Google'}
const models: Record<string,string[]> = {openai:[defaultModels.openai,'gpt-4.1'],anthropic:[defaultModels.anthropic,'claude-opus-5-5','claude-haiku-5-5'],google:[defaultModels.google,'gemini-2.5-pro']}
// The server's reference model wins wherever a provider offers it, so the quality note stays quiet by default.
const providerFor = (model:string) => Object.keys(models).find(provider=>models[provider].includes(model))
const modelFor = (provider:string, reference:string) => models[provider].includes(reference) ? reference : models[provider][0]
const states = 'Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|District of Columbia|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming'.split('|')
export function ShowcasePage() {
  const {t,i18n} = useTranslation('showcase')
  const qc = useQueryClient()
  const [key,setKey] = useState(readKey)
  const [notice,setNotice] = useState<{consent_text:string;idle_ttl_seconds?:number;reference_model?:string}>()
  const [consent,setConsent] = useState(false)
  const [story,setStory] = useState('')
  const [pdf,setPdf] = useState<File>()
  const [state,setState] = useState('')
  const [error,setError] = useState('')
  const [busy,setBusy] = useState(false)
  const [result,setResult] = useState<ResultsData>()
  const [viz,setViz] = useState<VisualizationData>()
  const [memo,setMemo] = useState('')
  const [reset,setReset] = useState(0)
  const [erase,setErase] = useState(false)
  const [idle,setIdle] = useState(false)
  const [expired,setExpired] = useState(false)
  const {pendingErases,queueErase} = usePendingErases()
  const [iterationLimit,setIterationLimit] = useState(false)
  const [session,setSession] = useState<{id:number;session_id:number;party_id:number} | null>(()=>JSON.parse(sessionStorage.getItem('showcase-intake') || 'null'))
  const lastActive = useRef(Date.now())
  const modelChosen = useRef(false)
  const generation = useRef(0)
  const analysisController = useRef<AbortController | null>(null)
  const erasing = useRef(false)
  const keepalive = useMemo(()=>session ? createSessionKeepalive(session.id,session.session_id) : undefined,[session])
  const recommended = notice?.reference_model || referenceModel
  useEffect(()=> { loadThemeFonts('courthouse-classic'); json('/api/v1/auth/showcase-notice').then(n=>{setNotice(n); if(n.reference_model && !modelChosen.current) setKey(k=>k.key?k:({...k,provider:providerFor(n.reference_model)??k.provider,model:n.reference_model}))}).catch(()=>setError('network')) },[])
  // Warm late-rendered children without letting namespace loading interrupt this page's effects.
  useEffect(()=> { void i18n.loadNamespaces(['chat', 'showcase']) },[i18n])
  useEffect(()=> { key.key ? sessionStorage.setItem('showcase-key',JSON.stringify(key)) : sessionStorage.removeItem('showcase-key') },[key])
  useEffect(()=>()=>analysisController.current?.abort(),[])
  useEffect(()=> {
    const activity = ()=>{ if(!idle && !expired && !erasing.current) {lastActive.current=Date.now();void keepalive?.().catch(()=>{})} }
    window.addEventListener('pointerdown',activity); window.addEventListener('keydown',activity)
    const timer = window.setInterval(()=> {
      const elapsed=Date.now()-lastActive.current, ttl=(notice?.idle_ttl_seconds || 3600)*1000
      if(elapsed>=ttl && !erasing.current && !expired) void end(true)
      else if(elapsed>=ttl-Math.min(60000,ttl/2)) setIdle(true)
    },1000)
    return ()=>{clearInterval(timer);window.removeEventListener('pointerdown',activity);window.removeEventListener('keydown',activity)}
  })
  function exportMemo() {
    const url=URL.createObjectURL(new Blob([memo],{type:'text/markdown'})); const a=document.createElement('a');a.href=url;a.download='folio-intake-memo.md';a.click();URL.revokeObjectURL(url)
  }
  async function end(expire=false) {
    if(erasing.current) return
    const intake=session
    const token=sessionStorage.getItem('showcase-token')
    erasing.current=true
    if(intake) queueErase({token,intakeId:intake.id})
    ++generation.current
    analysisController.current?.abort()
    for(const name of Object.keys(sessionStorage)) {
      if(name!==pendingEraseStorageKey) sessionStorage.removeItem(name)
    }
    setSession(null);setState('');setError('');setIterationLimit(false);setNonReference(false);setReset(n=>n+1);setStory('');setPdf(undefined);setResult(undefined);setViz(undefined);setMemo('');setKey({key:'',provider:providerFor(recommended)??'openai',model:providerFor(recommended)?recommended:defaultModels.openai});modelChosen.current=false;setConsent(false);setErase(false);setIdle(false);setExpired(expire);setBusy(false);qc.clear();lastActive.current=Date.now()
    erasing.current=false
  }

  const keyValid = key.provider==='google' ? /^AIza[\w-]{15,}$/.test(key.key) : key.provider==='anthropic' ? /^sk-ant-[\w-]{8,}$/.test(key.key) : /^sk-[\w-]{8,}$/.test(key.key)
  async function analyze() {
    setError('')
    if(!keyValid) {setError('keyError');document.getElementById('visitor-key')?.focus();return}
    if(!consent) {setError('consentRequired');return}
    if(!story.trim()&&!pdf) {setError('storyRequired');return}
    if(erasing.current) return
    setBusy(true);setResult(undefined);setViz(undefined);setIterationLimit(false)
    analysisController.current?.abort()
    const controller=new AbortController()
    analysisController.current=controller
    const runJson=async (path:string,body?:unknown)=>{
      controller.signal.throwIfAborted()
      const data=await json(path,body,{signal:controller.signal})
      controller.signal.throwIfAborted()
      return data
    }
    const run=++generation.current
    try {
      if(!sessionStorage.getItem('showcase-token')) {
        const guest=await runJson('/api/v1/auth/guest',{})
        sessionStorage.setItem('showcase-token',guest.access_token)
        await runJson('/api/v1/consent/grant',{consent_version:'1',consent_items:{ai_processing:true}})
      }
      let current=session
      if(!current) {current=await runJson('/api/v1/intake/',{});setSession(current);sessionStorage.setItem('showcase-intake',JSON.stringify(current))}
      if(!current) return
      qc.setQueryData(['intake',String(current.session_id),'progress'],{stage:1,totalStages:3,stageName:t('story'),completeness:0.1,iteration:1})
      if(pdf) {const form=new FormData();form.append('file',pdf);form.append('session_id',String(current.session_id));form.append('party_id',String(current.party_id));await request(`/api/v1/intake/${current.id}/document`,{method:'POST',body:form,signal:controller.signal})}
      const narrative=[story,state?`State confirmed by visitor: ${state}.`:''].filter(Boolean).join('\n\n')
      if((story.trim()||state) && !isStoryDelivered(current.session_id,narrative)) await sendStory(current.session_id,current.party_id,narrative,controller.signal)
      let status=await runJson(`/api/v1/analysis/${current.id}/analyze`,{})
      setNonReference(status.is_reference_model===false)
      while(!TERMINAL_ANALYSIS_STATUSES.includes(status.status)) {
        if(['failed','error'].includes(status.status)) throw new RequestError(500)
        if(run!==generation.current) return
        qc.setQueryData(['intake',String(current.session_id),'progress'],{stage:2,totalStages:3,stageName:status.latest_stage||t('issues'),completeness:(status.progress_pct||30)/100,iteration:status.iteration||1})
        await new Promise(resolve=>setTimeout(resolve,1500))
        status=await runJson(`/api/v1/analysis/${current.id}/status`)
      }
      const data=await runJson(`/api/v1/analysis/${current.id}/results`)
      const visualization=await runJson(`/api/v1/analysis/${current.id}/visualization`)
      const output=await runJson('/api/v1/output/generate',{intake_id:current.id,run_id:status.run_id,profile_types:['court_self_help']})
      const doc=output.documents[0] ? await runJson(`/api/v1/output/${output.documents[0].id}`) : null
      if(run!==generation.current) return
      setResult(data);setViz(visualization);setMemo(doc?.markdown_content||'');setIterationLimit(status.status==='max_iterations')
      const detected=data.jurisdiction || data.claims.find((c:{jurisdiction?:string})=>states.includes(c.jurisdiction||''))?.jurisdiction
      if(!state && states.includes(detected)) setState(detected)
    } catch(e) {
      if(run===generation.current && e instanceof RequestError && e.status===410) { void end(true); return }
      if(run===generation.current) setError(e instanceof RequestError ? e.status===401?'rejected':e.status===429?'quota':'failed':e instanceof TypeError?'network':'failed')
    } finally {if(run===generation.current) setBusy(false)}
  }
  const [nonReference,setNonReference]=useState(false)
  const stateControl=<fieldset className="state-control"><legend>{t('state',{state:state||t('unknown')})}</legend><p>{t('statePrompt')}</p><label>{t('stateLabel')}<select value={state} onChange={e=>setState(e.target.value)}><option value="">{t('stateOption')}</option>{states.map(s=><option key={s}>{s}</option>)}</select></label>{result&&<button disabled={busy} onClick={()=>void analyze()}>{t('confirmState')}</button>}</fieldset>
  return <ThemeProvider defaultTheme="courthouse-classic"><div className="showcase">
    <header className="showcase-banner"><div role="note">{t('banner')}</div></header>
    <main id="main-content"><header><h1>{t('title')}</h1><p>{t('intro')}</p></header>
    {pendingErases.some(pending=>pending.failed)&&<div role="alert">{t('eraseError',{defaultValue:'Local data was erased. The server could not confirm erasure; its session will expire automatically.'})}</div>}
    {expired ? <section><h2>{t('expired')}</h2><Button onClick={()=>{setExpired(false);lastActive.current=Date.now()}}>{t('fresh')}</Button></section> : <>
    {idle&&<aside role="alert"><p>{t('idle')}</p><button disabled={!memo} onClick={exportMemo}>{t('export')}</button><button onClick={()=>{lastActive.current=Date.now();setIdle(false);void keepalive?.().catch(()=>{})}}>{t('keep')}</button></aside>}
    <section className="showcase-inputs"><fieldset><legend>{t('key')}</legend><div className="key-fields">
      <label>{t('provider')}<select value={key.provider} onChange={e=>{const provider=e.target.value;modelChosen.current=true;setKey({...key,provider,model:modelFor(provider,recommended)})}}>{Object.entries(providers).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
      <label>{t('model')}<input list="showcase-models" value={key.model} onChange={e=>{modelChosen.current=true;setKey({...key,model:e.target.value})}}/><datalist id="showcase-models">{[...new Set([...models[key.provider],recommended])].map(m=><option key={m} value={m}/>)}</datalist></label>
      <label htmlFor="visitor-key">{t('key')}<input id="visitor-key" type="password" autoComplete="off" value={key.key} aria-invalid={!!key.key&&!keyValid} aria-describedby="key-privacy" onChange={e=>setKey({...key,key:e.target.value.trim()})}/></label></div>
      {key.key&&!keyValid&&<p>{t('keyError')}</p>}<p>{t('recommended',{model:recommended})}</p>
      <p>{t('keyHelp')} <a href={key.provider==='anthropic'?'https://console.anthropic.com/settings/keys':key.provider==='google'?'https://aistudio.google.com/apikey':'https://platform.openai.com/api-keys'} target="_blank" rel="noreferrer">{t('getKey')}</a></p><p id="key-privacy">{t('privacy')}</p>
      {(key.model!==recommended||nonReference)&&<p role="note">{t('reference',{model:recommended})}</p>}</fieldset>
      <label>{t('scenario')}<select key={reset} defaultValue="" onChange={e=>{const s=scenarios.find(s=>s.id===e.target.value);setStory(s?.story||'');setPdf(undefined);setState(s?'Minnesota':'')}}><option value="">{t('own')}</option>{scenarios.map(s=><option value={s.id} key={s.id}>{s.title} — {s.summary}</option>)}</select></label>
      <label>{t('story')}<textarea rows={9} value={story} onChange={e=>setStory(e.target.value)}/></label>
      <label>{t('pdf')}<input key={reset} type="file" accept="application/pdf" onChange={e=>setPdf(e.target.files?.[0])}/></label>
      {!result&&stateControl}
      {notice&&<label className="consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>{notice.consent_text}</label>}
      {error&&<div role="alert">{t(error)}</div>}
      <Button disabled={busy||!notice} onClick={()=>void analyze()}>{busy?t('busy'):error?t('retry'):t('analyze')}</Button>
      {busy&&<div role="status">{t('busy')}<Suspense fallback={null}><AnalysisProgressPanel sessionId={String(session?.session_id||'')}/></Suspense></div>}
    </section>
    {iterationLimit&&<p role="note">{t('iterationLimit',{defaultValue:'Analysis stopped at its iteration limit. The available results are shown below.'})}</p>}
    {result&&viz&&<Suspense fallback={null}><Results data={result} visualization={viz} memo={memo} stateControl={stateControl} exportMemo={exportMemo}/></Suspense>}
    {session&&<footer><button onClick={exportMemo} disabled={!memo}>{t('export')}</button><button onClick={()=>setErase(true)}>{t('end')}</button></footer>}
    <AlertDialog open={erase} onOpenChange={setErase}><AlertDialogContent><AlertDialogTitle>{t('confirmErase')}</AlertDialogTitle><AlertDialogDescription>{t('eraseDetails')}</AlertDialogDescription><AlertDialogAction onClick={()=>void end()}>{t('erase')}</AlertDialogAction><AlertDialogCancel>{t('cancel')}</AlertDialogCancel></AlertDialogContent></AlertDialog>
    </>}
    </main></div></ThemeProvider>
}
