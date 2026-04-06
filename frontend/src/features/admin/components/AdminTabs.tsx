import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useTranslation } from 'react-i18next'
import { OrgProfileForm } from './OrgProfileForm'
import { AutonomySettings } from './AutonomySettings'

export function AdminTabs() {
  const { t } = useTranslation('admin')
  return (
    <Tabs defaultValue="organization" className="w-full">
      <TabsList className="flex flex-wrap h-auto">
        <TabsTrigger value="organization" className="min-h-[44px]">
          {t('tabs.organization', 'Organization')}
        </TabsTrigger>
        <TabsTrigger value="research" className="min-h-[44px]">
          {t('tabs.research', 'Research Tools')}
        </TabsTrigger>
        <TabsTrigger value="kb" className="min-h-[44px]">
          {t('tabs.kb', 'Knowledge Base')}
        </TabsTrigger>
        <TabsTrigger value="protocols" className="min-h-[44px]">
          {t('tabs.protocols', 'Screening Protocols')}
        </TabsTrigger>
        <TabsTrigger value="profiles" className="min-h-[44px]">
          {t('tabs.profiles', 'Output Profiles')}
        </TabsTrigger>
        <TabsTrigger value="users" className="min-h-[44px]">
          {t('tabs.users', 'Users')}
        </TabsTrigger>
        <TabsTrigger value="usage" className="min-h-[44px]">
          {t('tabs.usage', 'Usage & Budgets')}
        </TabsTrigger>
        <TabsTrigger value="autonomy" className="min-h-[44px]">
          {t('tabs.autonomy', 'Autonomy')}
        </TabsTrigger>
      </TabsList>
      <TabsContent value="organization" className="pt-[24px]">
        <OrgProfileForm />
      </TabsContent>
      <TabsContent value="research" className="pt-[24px]">
        <p className="text-muted-foreground font-body text-[16px]">
          {t(
            'stub.research',
            'Research tool configuration -- integrates with Phase 6 admin API.'
          )}
        </p>
      </TabsContent>
      <TabsContent value="kb" className="pt-[24px]">
        <p className="text-muted-foreground font-body text-[16px]">
          {t(
            'stub.kb',
            'Knowledge base management -- integrates with Phase 6 KB admin API.'
          )}
        </p>
      </TabsContent>
      <TabsContent value="protocols" className="pt-[24px]">
        <p className="text-muted-foreground font-body text-[16px]">
          {t(
            'stub.protocols',
            'Screening protocol management -- integrates with Phase 5 protocol admin API.'
          )}
        </p>
      </TabsContent>
      <TabsContent value="profiles" className="pt-[24px]">
        <p className="text-muted-foreground font-body text-[16px]">
          {t(
            'stub.profiles',
            'Output profile configuration -- integrates with Phase 7 admin API.'
          )}
        </p>
      </TabsContent>
      <TabsContent value="users" className="pt-[24px]">
        <p className="text-muted-foreground font-body text-[16px]">
          {t(
            'stub.users',
            'User management -- integrates with Phase 1 user admin API.'
          )}
        </p>
      </TabsContent>
      <TabsContent value="usage" className="pt-[24px]">
        <p className="text-muted-foreground font-body text-[16px]">
          {t(
            'stub.usage',
            'Usage tracking + budget configuration -- future milestone.'
          )}
        </p>
      </TabsContent>
      <TabsContent value="autonomy" className="pt-[24px]">
        <AutonomySettings />
      </TabsContent>
    </Tabs>
  )
}
