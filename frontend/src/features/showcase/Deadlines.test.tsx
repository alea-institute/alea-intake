import { it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Deadlines } from './Deadlines'
import copy from '../../../public/locales/en/showcase.json'
vi.mock('react-i18next',()=>({useTranslation:()=>({t:(k:string,o?:Record<string,string>)=>Object.entries(o||{}).reduce((s,[key,v])=>s.replace(`{{${key}}}`,v),(copy as Record<string,string>)[k]||k)})}))
it('distinguishes deadline sources, lapsed dates and missing rules with cited evidence',()=>{
 render(<Deadlines deadlines={[
  {event_text:'File claim',status:'computed',computed_date:'2027-01-01',counting_method:'30 calendar days',citation:'Statute',citation_url:'https://www.revisor.mn.gov/',as_of_date:'2026-11-08'},
  {event_text:'Letter date',status:'document_stated'}, {event_text:'Contract',status:'contractual'}, {event_text:'Past',status:'lapsed'}, {event_text:'Unverified',status:'no_verified_rule'}, {event_text:'Where',status:'unknown_state'},
 ]}/>);
 expect(screen.getByText('2027-01-01')).toBeInTheDocument();expect(screen.getByText('How counted: 30 calendar days')).toBeInTheDocument();expect(screen.getByText('As of 2026-11-08')).toBeInTheDocument()
 expect(screen.getByRole('link',{name:'Statute'})).toHaveAttribute('href','https://www.revisor.mn.gov/')
 for (const label of ['Computed legal deadline','Date stated in your document','Contractual date — stated in your document, not a legal deadline','Deadline has lapsed','No verified rule for this deadline','Choose a state to check deadlines']) expect(screen.getByText(label)).toBeInTheDocument()
 expect(screen.getAllByRole('link',{name:'Find legal self-help'})).toHaveLength(2)
})
