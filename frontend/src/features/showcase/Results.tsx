import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NarrativeView } from '@/features/visualization/components/narrative/NarrativeView'
import { MatrixView } from '@/features/visualization/components/matrix/MatrixView'
import { GraphView } from '@/features/visualization/components/graph/GraphView'
import { AccessibleTable } from '@/features/visualization/components/AccessibleTable'
import { useGraphData } from '@/features/visualization/hooks/useGraphData'
import type { VisualizationData, ViewType } from '@/features/visualization/types'
import { MarkdownMemo } from '@/features/output/components/MarkdownMemo'
import { Deadlines, type Deadline } from './Deadlines'
export interface ResultsData { claims: {id:number;claim_name:string;folio_iri?:string}[]; deadlines: Deadline[] }
export function Results({data, visualization, memo, stateControl, exportMemo}: {data:ResultsData;visualization:VisualizationData;memo:string;stateControl:React.ReactNode;exportMemo:()=>void}) {
  const {t} = useTranslation('showcase')
  const [view,setView] = useState<ViewType|'deadlines'|'memo'>('narrative')
  const [table,setTable] = useState(false)
  const [graphTable,setGraphTable] = useState(() => window.matchMedia('(max-width: 600px)').matches)
  const showTable = view==='graph' ? graphTable : table
  const graph = useGraphData(visualization)
  const visual = view==='graph'||view==='matrix'||view==='narrative'
  return <section>
    <h2>{t('issues')}</h2>
    <div className="showcase-issues">{data.claims.map(c => <article key={c.id}><h3>{c.claim_name}</h3>{c.folio_iri && <a className="concept-chip" href={c.folio_iri} target="_blank" rel="noreferrer">{c.claim_name}</a>}</article>)}</div>
    <nav aria-label={t('issues')} className="showcase-tabs">{(['narrative','graph','matrix','deadlines','memo'] as const).map(v => <button key={v} aria-pressed={view===v} onClick={()=>setView(v)}>{t(v)}</button>)}</nav>
    <div role="status" className="sr-only">{t(view)}</div>
    {visual && <label><input type="checkbox" checked={showTable} onChange={e=>view==='graph'?setGraphTable(e.target.checked):setTable(e.target.checked)}/>{t('table')}</label>}
    <div className={view==='narrative'?'showcase-narrative':'showcase-visual'} role="region" aria-label={t('region',{view:t(view)})} tabIndex={0}>
      {visual && showTable ? <AccessibleTable mode={view as ViewType} data={visualization}/> : <>
        {view==='narrative' && <NarrativeView data={visualization}/>}
        {view==='matrix' && <MatrixView data={visualization}/>}
        {view==='graph' && <div className="showcase-graph"><GraphView {...graph} width={800} height={480}/></div>}
      </>}
      {view==='deadlines' && <>{stateControl}<Deadlines deadlines={data.deadlines}/></>}
      {view==='memo' && <><button onClick={exportMemo}>{t('export')}</button><MarkdownMemo content={memo}/></>}
    </div>
  </section>
}
