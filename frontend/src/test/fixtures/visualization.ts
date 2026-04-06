/**
 * Mock visualization data for tests and MSW handlers.
 *
 * Realistic landlord-tenant dispute scenario:
 * - 3 facts about habitability issues
 * - 2 claims (breach of warranty of habitability, wrongful eviction)
 * - 4 elements across both claims
 * - 5 mappings linking facts to elements
 * - 2 gaps (missing evidence)
 * - 3 messages (consumer narrative, professional question, consumer response)
 */

import type { VisualizationData } from '@/features/visualization/types'

export const mockVisualizationData: VisualizationData = {
  run_id: 1,
  status: 'completed',

  facts: [
    {
      id: 101,
      assertion_text: 'Landlord has refused to fix the broken heater since November 2025',
      fact_type: 'assertion',
      confidence: 0.92,
      source_spans: [
        {
          message_id: 301,
          start_char: 0,
          end_char: 64,
          page_number: null,
          paragraph_index: null,
          timestamp_start_sec: null,
          timestamp_end_sec: null,
        },
      ],
    },
    {
      id: 102,
      assertion_text: 'Apartment has visible mold in the bathroom and kitchen',
      fact_type: 'condition',
      confidence: 0.88,
      source_spans: [
        {
          message_id: 303,
          start_char: 20,
          end_char: 74,
          page_number: null,
          paragraph_index: null,
          timestamp_start_sec: null,
          timestamp_end_sec: null,
        },
      ],
    },
    {
      id: 103,
      assertion_text: 'Landlord served a 30-day notice to vacate after tenant complained',
      fact_type: 'event',
      confidence: 0.85,
      source_spans: [
        {
          message_id: 301,
          start_char: 120,
          end_char: 184,
          page_number: null,
          paragraph_index: null,
          timestamp_start_sec: null,
          timestamp_end_sec: null,
        },
      ],
    },
  ],

  claims: [
    {
      id: 201,
      claim_name: 'Breach of Warranty of Habitability',
      claim_type: 'identified',
      jurisdiction: 'California',
      confidence: 0.85,
      rationale:
        'Landlord failed to maintain habitable conditions by not repairing heating and allowing mold growth',
      elements: [
        {
          id: 401,
          element_name: 'Defective Condition',
          element_description:
            'The rental unit has a condition that substantially impairs health and safety',
          is_satisfied: true,
          satisfaction_confidence: 0.90,
        },
        {
          id: 402,
          element_name: 'Notice to Landlord',
          element_description:
            'Tenant gave landlord reasonable notice of the defective condition',
          is_satisfied: false,
          satisfaction_confidence: 0.30,
        },
        {
          id: 403,
          element_name: 'Reasonable Time to Repair',
          element_description: 'Landlord was given a reasonable time to make repairs',
          is_satisfied: true,
          satisfaction_confidence: 0.75,
        },
      ],
    },
    {
      id: 202,
      claim_name: 'Wrongful Eviction / Retaliatory Eviction',
      claim_type: 'potential',
      jurisdiction: 'California',
      confidence: 0.60,
      rationale:
        'Eviction notice served shortly after tenant complaints suggests retaliation',
      elements: [
        {
          id: 404,
          element_name: 'Protected Activity',
          element_description: 'Tenant engaged in a legally protected activity (complaint)',
          is_satisfied: true,
          satisfaction_confidence: 0.82,
        },
      ],
    },
  ],

  mappings: [
    {
      id: 501,
      fact_id: 101,
      claim_id: 201,
      element_id: 401,
      confidence: 0.88,
      mapping_rationale: 'Broken heater constitutes defective condition affecting habitability',
    },
    {
      id: 502,
      fact_id: 102,
      claim_id: 201,
      element_id: 401,
      confidence: 0.82,
      mapping_rationale: 'Mold growth in multiple rooms is a health hazard and defective condition',
    },
    {
      id: 503,
      fact_id: 101,
      claim_id: 201,
      element_id: 403,
      confidence: 0.75,
      mapping_rationale: 'Heater broken since November 2025 indicates landlord had reasonable time',
    },
    {
      id: 504,
      fact_id: 103,
      claim_id: 202,
      element_id: 404,
      confidence: 0.78,
      mapping_rationale: 'Eviction notice after complaint suggests retaliatory motive',
    },
    {
      id: 505,
      fact_id: 101,
      claim_id: 202,
      element_id: 404,
      confidence: 0.65,
      mapping_rationale: 'Complaint about heater is protected activity that preceded eviction',
    },
  ],

  gaps: [
    {
      id: 601,
      gap_type: 'unsupported_element',
      claim_id: 201,
      element_id: 402,
      description: 'No evidence that tenant formally notified landlord of defective conditions',
      priority: 1,
      status: 'open',
    },
    {
      id: 602,
      gap_type: 'weak_mapping',
      claim_id: 202,
      element_id: null,
      description:
        'Timeline between complaint and eviction notice needs clarification for retaliation claim',
      priority: 2,
      status: 'open',
    },
  ],

  messages: [
    {
      id: 301,
      content:
        'Landlord has refused to fix the broken heater since November 2025. I have been asking repeatedly but nothing has been done. Then last week he served me a 30-day notice to vacate after I complained about the conditions.',
      sender_type: 'consumer',
    },
    {
      id: 302,
      content:
        'Can you tell me more about the conditions in the apartment? Are there other maintenance issues beyond the heater?',
      sender_type: 'professional',
    },
    {
      id: 303,
      content:
        'Yes, there is also visible mold in the bathroom and kitchen that has been growing for months. The landlord knows about it but has not done anything.',
      sender_type: 'consumer',
    },
  ],
}
