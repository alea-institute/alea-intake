import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  MessageSquarePlus,
  Settings,
  type LucideIcon,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/features/auth/store'
import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  icon: LucideIcon
  labelKey: string
  requireAdmin?: boolean
}

const ITEMS: NavItem[] = [
  { to: '/dashboard', icon: LayoutDashboard, labelKey: 'nav.dashboard' },
  { to: '/chat/new', icon: MessageSquarePlus, labelKey: 'nav.newIntake' },
  { to: '/admin', icon: Settings, labelKey: 'nav.admin', requireAdmin: true },
]

export function Sidebar() {
  const { t } = useTranslation('common')
  const user = useAuth((s) => s.user)
  const isAdmin = user?.role === 'admin'

  return (
    <nav
      className="hidden sm:flex flex-col bg-card border-r border-border w-14 md:w-14 lg:w-60 shrink-0"
      aria-label={t('a11y.primaryNav', 'Primary navigation')}
    >
      <ul className="flex flex-col gap-[4px] p-[8px]">
        {ITEMS.filter((i) => !i.requireAdmin || isAdmin).map(
          ({ to, icon: Icon, labelKey }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-[16px] rounded-md min-h-[44px] px-[8px] transition-colors outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
                    isActive
                      ? 'bg-primary text-primary-foreground'
                      : 'text-foreground hover:bg-secondary'
                  )
                }
                aria-label={t(labelKey)}
              >
                <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                <span className="hidden lg:inline font-body text-[16px]">
                  {t(labelKey)}
                </span>
              </NavLink>
            </li>
          )
        )}
      </ul>
    </nav>
  )
}
