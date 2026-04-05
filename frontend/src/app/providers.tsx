import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Suspense, type ReactNode } from 'react'
import { I18nextProvider } from 'react-i18next'
import i18n from '@/shared/i18n/config'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
  },
})

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <I18nextProvider i18n={i18n}>
        <Suspense fallback={<div className="p-8">Loading…</div>}>{children}</Suspense>
      </I18nextProvider>
    </QueryClientProvider>
  )
}

export { queryClient }
