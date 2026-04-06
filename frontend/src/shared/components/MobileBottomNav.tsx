import { NavLink } from 'react-router-dom'
import {
  MessageSquare,
  LayoutDashboard,
  Settings,
  User,
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
  { to: '/chat/new', icon: MessageSquare, labelKey: 'nav.chat' },
  { to: '/dashboard', icon: LayoutDashboard, labelKey: 'nav.dashboard' },
  { to: '/admin', icon: Settings, labelKey: 'nav.admin', requireAdmin: true },
  { to: '/profile', icon: User, labelKey: 'nav.profile' },
]

export function MobileBottomNav() {
  const { t } = useTranslation('common')
  const user = useAuth((s) => s.user)
  const isAdmin = user?.role === 'admin'
  const items = ITEMS.filter((i) => !i.requireAdmin || isAdmin)

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 sm:hidden bg-card border-t border-border h-[64px] flex items-stretch z-40"
      aria-label={t('a11y.mobileNav', 'Primary mobile navigation')}
    >
      {items.map(({ to, icon: Icon, labelKey }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            cn(
              'flex-1 flex flex-col items-center justify-center gap-[4px] min-h-[44px] min-w-[44px] outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
              isActive ? 'text-primary' : 'text-muted-foreground'
            )
          }
          aria-label={t(labelKey)}
        >
          <Icon className="h-5 w-5" aria-hidden="true" />
          <span className="text-[12px] font-body">{t(labelKey)}</span>
        </NavLink>
      ))}
    </nav>
  )
}
