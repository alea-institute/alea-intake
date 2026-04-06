import { useTranslation } from 'react-i18next'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { Phone } from 'lucide-react'
import { useSafetyUI } from '../store'
import { useSafetyAlerts } from '../hooks/useSafetyAlerts'

interface Props { sessionId: string }

interface DefaultHotline { name: string; phone: string }

const DEFAULT_HOTLINES: DefaultHotline[] = [
  { name: 'National Domestic Violence Hotline', phone: '1-800-799-7233' },
  { name: '988 Suicide & Crisis Lifeline', phone: '988' },
  { name: 'Childhelp National Child Abuse Hotline', phone: '1-800-422-4453' },
]

export function SafetyDrawer({ sessionId }: Props) {
  const { t } = useTranslation('safety')
  const drawerOpen = useSafetyUI((s) => s.drawerOpen)
  const setDrawerOpen = useSafetyUI((s) => s.setDrawerOpen)
  const { data: alerts = [] } = useSafetyAlerts(sessionId)

  // Merge alert-specific resources with default hotlines
  const alertResources = alerts.flatMap((a) => a.resources)
  const mergedHotlines = [
    ...DEFAULT_HOTLINES,
    ...alertResources.filter((r) => r.phone).map((r) => ({ name: r.name, phone: r.phone ?? '' })),
  ]

  return (
    <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
      <SheetContent side="right" className="sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="font-display text-[20px]">{t('critical.drawer.heading', 'Are you safe right now?')}</SheetTitle>
          <SheetDescription>{t('critical.drawer.body', 'If you are in immediate danger, call 911. The resources below can help you find support.')}</SheetDescription>
        </SheetHeader>
        <ul className="mt-lg space-y-md" aria-label={t('critical.drawer.hotlinesLabel', 'Safety hotlines')}>
          {mergedHotlines.map((h, i) => (
            <li key={i} className="border border-border rounded-md p-md">
              <p className="font-body text-[16px] font-medium">{h.name}</p>
              <a
                href={`tel:${h.phone.replace(/[^0-9]/g, '')}`}
                className="inline-flex items-center gap-xs text-primary underline font-body text-[16px] mt-xs min-h-[44px]"
              >
                <Phone className="h-4 w-4" aria-hidden="true" />
                {h.phone}
              </a>
            </li>
          ))}
        </ul>
      </SheetContent>
    </Sheet>
  )
}
