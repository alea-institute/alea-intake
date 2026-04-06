import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/msw/server'
import { renderWithProviders } from '@/test/utils'
import { AdminTabs } from './AdminTabs'

function setupAutonomyHandlers() {
  server.use(
    http.get('/api/v1/autonomy/admin/config', () =>
      HttpResponse.json({
        stage_checkpoints: {},
        timeout_seconds: 300,
        timeout_behavior: 'auto_proceed',
        safety_behavior: 'strict',
        notify_websocket: true,
        notify_email: false,
        labels: {},
      })
    ),
    http.get('/api/v1/autonomy/admin/stages', () => HttpResponse.json([])),
    http.get('/api/v1/autonomy/admin/presets', () => HttpResponse.json({})),
  )
}

describe('AdminTabs', () => {
  it('renders 8 tab triggers', () => {
    setupAutonomyHandlers()
    renderWithProviders(<AdminTabs />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(8)
  })

  it('Organization tab is active by default', () => {
    renderWithProviders(<AdminTabs />)
    const orgTab = screen.getByRole('tab', { name: /organization/i })
    expect(orgTab).toHaveAttribute('data-state', 'active')
  })

  it('clicking Research Tools tab switches active content', async () => {
    renderWithProviders(<AdminTabs />)
    const researchTab = screen.getByRole('tab', { name: /research/i })
    await userEvent.click(researchTab)
    expect(researchTab).toHaveAttribute('data-state', 'active')
  })
})
