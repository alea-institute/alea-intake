import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import type { OutputProfileData } from '../api'
import { MarkdownMemo } from './MarkdownMemo'

interface Props {
  profiles: OutputProfileData[]
}

const PROFILE_LABELS: Record<string, string> = {
  law_firm_memo: 'Law Firm Memo',
  consumer_summary: 'Consumer Summary',
  triage_routing: 'Triage & Routing',
  self_help_guidance: 'Self-Help Guidance',
}

export function ProfileTabs({ profiles }: Props) {
  if (profiles.length === 0) return null
  return (
    <Tabs defaultValue={profiles[0].profile_key} className="w-full">
      <TabsList>
        {profiles.map((p) => (
          <TabsTrigger
            key={p.profile_key}
            value={p.profile_key}
            className="min-h-[44px]"
          >
            {PROFILE_LABELS[p.profile_key] ?? p.profile_key}
          </TabsTrigger>
        ))}
      </TabsList>
      {profiles.map((p) => (
        <TabsContent
          key={p.profile_key}
          value={p.profile_key}
          className="pt-[24px]"
        >
          <MarkdownMemo content={p.content} />
        </TabsContent>
      ))}
    </Tabs>
  )
}
