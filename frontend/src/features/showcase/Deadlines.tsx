import { useTranslation } from 'react-i18next'
export interface Deadline {
  event_text: string; computed_date?: string; computed?: boolean; event_type?: string; status?: string
  citation?: string; citation_url?: string; counting_method?: string; as_of_date?: string
  hedge?: string; jurisdiction?: string; self_help_url?: string
  /** Memo-style heading ("label — date") and server-side lapsed flag from /results. */
  heading?: string; lapsed?: boolean
}
export function Deadlines({deadlines}: {deadlines: Deadline[]}) {
  const {t} = useTranslation('showcase')
  const help = 'https://www.lawhelp.org/'
  return <section className="deadline-list">
    {!deadlines.length && <p>{t('noDeadlines')} <a href={help}>{t('selfHelp')}</a></p>}
    {deadlines.map((d,i) => {
      const kind = d.status || (d.event_type === 'contractual' ? 'contractual' : d.computed_date && d.computed ? ((d.lapsed ?? d.computed_date < new Date().toISOString().slice(0,10)) ? 'lapsed' : 'computed') : d.event_type === 'document_stated' ? 'document_stated' : d.jurisdiction === 'unknown' ? 'unknown_state' : 'no_verified_rule')
      return <article key={i} className={`deadline deadline-${kind}`}>
        <h3>{d.heading ?? d.event_text}</h3><strong>{t(kind)}</strong>
        {d.heading && d.event_text && <p className="deadline-quote">{t('inYourWords',{quote:d.event_text})}</p>}
        {d.computed_date && <p><time>{d.computed_date}</time></p>}
        {d.counting_method && <p>{t('counted',{method:d.counting_method})}</p>}
        {d.citation && <p>{d.citation_url ? <a href={d.citation_url} target="_blank" rel="noreferrer">{d.citation}</a> : d.citation}</p>}
        {d.as_of_date && <p>{t('asOf',{date:d.as_of_date})}</p>}
        {d.hedge && <p>{d.hedge}</p>}
        {['no_verified_rule','unknown_state'].includes(kind) && <a href={d.self_help_url || help}>{t('selfHelp')}</a>}
      </article>
    })}
  </section>
}
