import { AlertDialog, AlertDialogContent, AlertDialogTitle, AlertDialogDescription, AlertDialogAction, AlertDialogCancel } from '@/components/ui/alert-dialog'
import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { AnalysisProgressPanel } from '@/features/chat/components/AnalysisProgressPanel'
import { ThemeProvider } from '@/shared/components/ThemeProvider'
import { loadThemeFonts } from '@/shared/i18n/themes'
import type { VisualizationData } from '@/features/visualization/types'
import { Results, type ResultsData } from './Results'
import { defaultModels, json, readKey, referenceModel, request, RequestError, sendStory } from './session'
import scenarios from './scenarios.json'
import './showcase.css'

const providers = {openai:'OpenAI',anthropic:'Anthropic',google:'Google'}
const models: Record<string,string[]> = {openai:[defaultModels.openai,'gpt-4.1'],anthropic:[defaultModels.anthropic,'claude-sonnet-4-5'],google:[defaultModels.google,'gemini-2.5-pro']}
const states = 'Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|District of Columbia|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming'.split('|')
export function ShowcasePage() {
  const {t} = useTranslation('showcase')
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
  const [ending,setEnding] = useState(false)
  const [session,setSession] = useState<{id:number;session_id:number;party_id:number} | null>(()=>JSON.parse(sessionStorage.getItem('showcase-intake') || 'null'))
  const lastActive = useRef(Date.now())
  const generation = useRef(0)
  const recommended = notice?.reference_model || referenceModel
  useEffect(()=> { loadThemeFonts('courthouse-classic'); json('/api/v1/auth/showcase-notice').then(n=>{setNotice(n); if(n.reference_model) setKey(k=>k.key?k:({...k,model:n.reference_model}))}).catch(()=>setError('network')) },[])
  useEffect(()=> { key.key ? sessionStorage.setItem('showcase-key',JSON.stringify(key)) : sessionStorage.removeItem('showcase-key') },[key])
  useEffect(()=> {
    const activity = ()=>{ if(!idle && !expired) lastActive.current=Date.now() }
    window.addEventListener('pointerdown',activity); window.addEventListener('keydown',activity)
    const timer = window.setInterval(()=> {
      const elapsed=Date.now()-lastActive.current, ttl=(notice?.idle_ttl_seconds || 3600)*1000
      if(elapsed>=ttl && !ending && !expired) void end(true)
      else if(elapsed>=ttl-Math.min(60000,ttl/2)) setIdle(true)
    },1000)
    return ()=>{clearInterval(timer);window.removeEventListener('pointerdown',activity);window.removeEventListener('keydown',activity)}
  })
  function exportMemo() {
    const url=URL.createObjectURL(new Blob([memo],{type:'text/markdown'})); const a=document.createElement('a');a.href=url;a.download='folio-intake-memo.md';a.click();URL.revokeObjectURL(url)
  }
  async function end(expire=false) {
    setEnding(true); generation.current++
    try {
      if(session) await request(`/api/v1/intake/${session.id}/end-session`,{method:'POST'})
      for(const name of ['showcase-token','showcase-intake','showcase-key']) sessionStorage.removeItem(name)
      setSession(null);setState('');setError('');setNonReference(false);setReset(n=>n+1);setStory('');setPdf(undefined);setResult(undefined);setViz(undefined);setMemo('');setKey({key:'',provider:'openai',model:defaultModels.openai});setConsent(false);setErase(false);setIdle(false);setExpired(expire);setBusy(false);qc.clear();lastActive.current=Date.now()
    } catch {setError('network')} finally {setEnding(false)}
  }
  const keyValid = key.provider==='google' ? /^AIza[\w-]{15,}$/.test(key.key) : key.provider==='anthropic' ? /^sk-ant-[\w-]{8,}$/.test(key.key) : /^sk-[\w-]{8,}$/.test(key.key)
  async function analyze() {
    setError('')
    if(!keyValid) {setError('keyError');document.getElementById('visitor-key')?.focus();return}
    if(!consent) {setError('consentRequired');return}
    if(!story.trim()&&!pdf) {setError('storyRequired');return}
    setBusy(true);setResult(undefined);setViz(undefined)
    const run=++generation.current
    try {
      if(!sessionStorage.getItem('showcase-token')) {
        const guest=await json('/api/v1/auth/guest',{})
        sessionStorage.setItem('showcase-token',guest.access_token)
        await json('/api/v1/consent/grant',{consent_version:'1',consent_items:{ai_processing:true}})
      }
      let current=session
      if(!current) {current=await json('/api/v1/intake/',{});setSession(current);sessionStorage.setItem('showcase-intake',JSON.stringify(current))}
      if(!current) return
      qc.setQueryData(['intake',String(current.session_id),'progress'],{stage:1,totalStages:3,stageName:t('story'),completeness:0.1,iteration:1})
      if(pdf) {const form=new FormData();form.append('file',pdf);form.append('session_id',String(current.session_id));form.append('party_id',String(current.party_id));await request(`/api/v1/intake/${current.id}/document`,{method:'POST',body:form})}
      if(story.trim()||state) await sendStory(current.session_id,current.party_id,[story,state?`State confirmed by visitor: ${state}.`:''].filter(Boolean).join('\n\n'))
      let status=await json(`/api/v1/analysis/${current.id}/analyze`,{})
      setNonReference(status.is_reference_model===false)
      while(!['completed','complete','converged'].includes(status.status)) {
        if(['failed','error'].includes(status.status)) throw new RequestError(500)
        if(run!==generation.current) return
        qc.setQueryData(['intake',String(current.session_id),'progress'],{stage:2,totalStages:3,stageName:status.latest_stage||t('issues'),completeness:(status.progress_pct||30)/100,iteration:status.iteration||1})
        await new Promise(resolve=>setTimeout(resolve,1500))
        status=await json(`/api/v1/analysis/${current.id}/status`)
      }
      const data=await json(`/api/v1/analysis/${current.id}/results`)
      const visualization=await json(`/api/v1/analysis/${current.id}/visualization`)
      const output=await json('/api/v1/output/generate',{intake_id:current.id,run_id:status.run_id,profile_types:['court_self_help']})
      const doc=output.documents[0] ? await json(`/api/v1/output/${output.documents[0].id}`) : null
      if(run!==generation.current) return
      setResult(data);setViz(visualization);setMemo(doc?.markdown_content||'')
      const detected=data.jurisdiction || data.claims.find((c:{jurisdiction?:string})=>states.includes(c.jurisdiction||''))?.jurisdiction
      if(!state && states.includes(detected)) setState(detected)
    } catch(e) {
      if(run===generation.current) setError(e instanceof RequestError ? e.status===401?'rejected':e.status===429?'quota':'failed':e instanceof TypeError?'network':'failed')
    } finally {if(run===generation.current) setBusy(false)}
  }
  const [nonReference,setNonReference]=useState(false)
  const stateControl=<fieldset className="state-control"><legend>{t('state',{state:state||t('unknown')})}</legend><p>{t('statePrompt')}</p><label>{t('stateLabel')}<select value={state} onChange={e=>setState(e.target.value)}><option value="">{t('stateOption')}</option>{states.map(s=><option key={s}>{s}</option>)}</select></label>{result&&<button disabled={busy} onClick={()=>void analyze()}>{t('confirmState')}</button>}</fieldset>
  return <ThemeProvider defaultTheme="courthouse-classic"><div className="showcase">
    <header className="showcase-banner"><div role="note">{t('banner')}</div></header>
    <main id="main-content"><header><h1>{t('title')}</h1><p>{t('intro')}</p></header>
    {ending ? <p role="status">{t('pendingErase')}</p> : expired ? <section><h2>{t('expired')}</h2><Button onClick={()=>{setExpired(false);lastActive.current=Date.now()}}>{t('fresh')}</Button></section> : <>
    {idle&&<aside role="alert"><p>{t('idle')}</p><button disabled={!memo} onClick={exportMemo}>{t('export')}</button><button onClick={()=>{lastActive.current=Date.now();setIdle(false);if(session) void json(`/api/v1/analysis/${session.id}/results`).catch(()=>setError('network'))}}>{t('keep')}</button></aside>}
    <section className="showcase-inputs"><fieldset><legend>{t('key')}</legend><div className="key-fields">
      <label>{t('provider')}<select value={key.provider} onChange={e=>{const provider=e.target.value;setKey({...key,provider,model:models[provider][0]})}}>{Object.entries(providers).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
      <label>{t('model')}<input list="showcase-models" value={key.model} onChange={e=>setKey({...key,model:e.target.value})}/><datalist id="showcase-models">{[...new Set([...models[key.provider],recommended])].map(m=><option key={m} value={m}/>)}</datalist></label>
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
      {busy&&<div role="status">{t('busy')}<AnalysisProgressPanel sessionId={String(session?.session_id||'')}/></div>}
    </section>
    {result&&viz&&<Results data={result} visualization={viz} memo={memo} stateControl={stateControl} exportMemo={exportMemo}/>}
    {session&&<footer><button onClick={exportMemo} disabled={!memo}>{t('export')}</button><button onClick={()=>setErase(true)}>{t('end')}</button></footer>}
    <AlertDialog open={erase} onOpenChange={setErase}><AlertDialogContent><AlertDialogTitle>{t('confirmErase')}</AlertDialogTitle><AlertDialogDescription>{t('eraseDetails')}</AlertDialogDescription><AlertDialogAction onClick={()=>void end()}>{t('erase')}</AlertDialogAction><AlertDialogCancel>{t('cancel')}</AlertDialogCancel></AlertDialogContent></AlertDialog>
    </>}
    </main></div></ThemeProvider>
}
