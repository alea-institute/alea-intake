import type { VisualizationData } from '@/features/visualization/types'
import scenarios from '@/features/showcase/scenarios.json' with { type: 'json' }

const story = scenarios.find(scenario => scenario.id === 'wage-theft')!.story
const evidence = [
  'HE tells me what job site to be at and what time',
  '108 hours',
  'dont bother coming monday, im going a different direction.',
]

export const wageTheftVisualization: VisualizationData = {
  run_id: 4,
  status: 'completed',
  messages: [{id:301, content:story, sender_type:'consumer'}],
  facts: evidence.map((text, index) => ({
    id:101+index, assertion_text:text, fact_type:'assertion', confidence:0.9,
    source_spans:[{message_id:301,start_char:story.indexOf(text),end_char:story.indexOf(text)+text.length,
      page_number:null,paragraph_index:null,timestamp_start_sec:null,timestamp_end_sec:null}],
  })),
  claims: [
    {id:201,claim_name:'Unpaid wages',claim_type:'identified',jurisdiction:'Minnesota',confidence:0.9,
      rationale:'The worker reports two unpaid weeks after termination.',
      elements:[
        {id:401,element_name:'Employment relationship',element_description:'Employer directs the work.',is_satisfied:true,satisfaction_confidence:0.9},
        {id:402,element_name:'Wages owed',element_description:'Work performed without payment.',is_satisfied:true,satisfaction_confidence:0.9},
      ]},
    {id:202,claim_name:'Unpaid overtime',claim_type:'potential',jurisdiction:'Minnesota',confidence:0.85,
      rationale:'The worker reports 54 to 56 hours a week paid at straight time.',
      elements:[{id:403,element_name:'Overtime hours',element_description:'Hours worked beyond the applicable threshold.',is_satisfied:true,satisfaction_confidence:0.85}]},
    {id:203,claim_name:'Retaliatory discharge',claim_type:'potential',jurisdiction:'Minnesota',confidence:0.8,
      rationale:'Termination followed the request for overtime pay.',
      elements:[{id:404,element_name:'Adverse employment action',element_description:'Worker was dismissed after raising overtime concerns.',is_satisfied:true,satisfaction_confidence:0.8}]},
  ],
  mappings:[
    {id:501,fact_id:101,claim_id:201,element_id:401,confidence:0.9,mapping_rationale:'Employer controls job sites and schedule.'},
    {id:502,fact_id:102,claim_id:201,element_id:402,confidence:0.9,mapping_rationale:'108 hours reported unpaid.'},
    {id:503,fact_id:102,claim_id:202,element_id:403,confidence:0.85,mapping_rationale:'Two weeks total 108 hours.'},
    {id:504,fact_id:103,claim_id:203,element_id:404,confidence:0.8,mapping_rationale:'Dismissal text followed the overtime complaint.'},
  ],
  gaps:[{id:601,gap_type:'missing_evidence',claim_id:201,element_id:402,
    description:'Review the hours notebook and payment records to confirm the unpaid amount.',priority:1,status:'open'}],
}
