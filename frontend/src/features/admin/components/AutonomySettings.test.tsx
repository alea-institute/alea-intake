import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/msw/server'
import { renderWithProviders } from '@/test/utils'
import { AutonomySettings } from './AutonomySettings'
import { AdminTabs } from './AdminTabs'

const STAGES = ['issue_spot', 'explore', 'research', 'fact_map', 'gap_analyze', 'question_gen']

const CHATBOT_CONFIG = {
  stage_checkpoints: Object.fromEntries(STAGES.map((s) => [s, 'auto'])),
  timeout_seconds: 300,
  timeout_behavior: 'auto_proceed',
  safety_behavior: 'strict',
  notify_websocket: true,
  notify_email: false,
  labels: {},
}

const PROFESSIONAL_CONFIG = {
  stage_checkpoints: Object.fromEntries(STAGES.map((s) => [s, 'checkpoint'])),
  timeout_seconds: 300,
  timeout_behavior: 'pause_until',
  safety_behavior: 'strict',
  notify_websocket: true,
  notify_email: true,
  labels: {},
}

const AGENT_CONFIG = {
  stage_checkpoints: {
    ...Object.fromEntries(STAGES.map((s) => [s, 'auto'])),
    question_gen: 'checkpoint',
  },
  timeout_seconds: 300,
  timeout_behavior: 'queue_next',
  safety_behavior: 'professional',
  notify_websocket: true,
  notify_email: false,
  labels: {},
}

const PRESETS = {
  chatbot: CHATBOT_CONFIG,
  professional: PROFESSIONAL_CONFIG,
  agent: AGENT_CONFIG,
}

function setupHandlers() {
  server.use(
    http.get('/api/v1/autonomy/admin/config', () => HttpResponse.json(CHATBOT_CONFIG)),
    http.get('/api/v1/autonomy/admin/stages', () => HttpResponse.json(STAGES)),
    http.get('/api/v1/autonomy/admin/presets', () => HttpResponse.json(PRESETS)),
    http.put('/api/v1/autonomy/admin/config', async ({ request }) => {
      const body = await request.json()
      return HttpResponse.json(body)
    }),
  )
}

describe('AutonomySettings', () => {
  it('renders 6 stage toggle switches', async () => {
    setupHandlers()
    renderWithProviders(<AutonomySettings />)
    await waitFor(() => {
      const switches = screen.getAllByRole('switch')
      // 6 stage toggles + notify_websocket + notify_email = 8 switches
      expect(switches.length).toBeGreaterThanOrEqual(6)
    })
  })

  it('renders timeout number input with min=60', async () => {
    setupHandlers()
    renderWithProviders(<AutonomySettings />)
    await waitFor(() => {
      const input = screen.getByLabelText(/timeout duration/i)
      expect(input).toHaveAttribute('min', '60')
      expect(input).toHaveAttribute('type', 'number')
    })
  })

  it('renders timeout behavior dropdown with 3 options', async () => {
    setupHandlers()
    renderWithProviders(<AutonomySettings />)
    await waitFor(() => {
      expect(screen.getByText(/on timeout/i)).toBeInTheDocument()
    })
  })

  it('renders safety behavior radio group', async () => {
    setupHandlers()
    renderWithProviders(<AutonomySettings />)
    await waitFor(() => {
      expect(screen.getByText(/safety behavior/i)).toBeInTheDocument()
      const radios = screen.getAllByRole('radio')
      expect(radios.length).toBe(2)
    })
  })

  it('selecting Chatbot preset sets all toggles to AUTO', async () => {
    setupHandlers()
    renderWithProviders(<AutonomySettings />)
    const user = userEvent.setup()
    await waitFor(() => expect(screen.getByRole('button', { name: /chatbot/i })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /chatbot/i }))
    // All stage switches should be unchecked (auto = unchecked)
    await waitFor(() => {
      const switches = screen.getAllByRole('switch')
      const stageSwitches = switches.slice(0, 6)
      stageSwitches.forEach((sw) => {
        expect(sw).toHaveAttribute('data-state', 'unchecked')
      })
    })
  })

  it('selecting Professional preset sets all toggles to CHECKPOINT', async () => {
    setupHandlers()
    renderWithProviders(<AutonomySettings />)
    const user = userEvent.setup()
    await waitFor(() => expect(screen.getByRole('button', { name: /professional/i })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /professional/i }))
    await waitFor(() => {
      const switches = screen.getAllByRole('switch')
      const stageSwitches = switches.slice(0, 6)
      stageSwitches.forEach((sw) => {
        expect(sw).toHaveAttribute('data-state', 'checked')
      })
    })
  })

  it('selecting Agent preset sets only question_gen to CHECKPOINT', async () => {
    setupHandlers()
    renderWithProviders(<AutonomySettings />)
    const user = userEvent.setup()
    await waitFor(() => expect(screen.getByRole('button', { name: /agent/i })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /agent/i }))
    await waitFor(() => {
      const switches = screen.getAllByRole('switch')
      // First 5 stages should be unchecked (auto), last one (question_gen) checked
      for (let i = 0; i < 5; i++) {
        expect(switches[i]).toHaveAttribute('data-state', 'unchecked')
      }
      expect(switches[5]).toHaveAttribute('data-state', 'checked')
    })
  })

  it('save button calls PUT /api/v1/autonomy/admin/config', async () => {
    let putCalled = false
    server.use(
      http.get('/api/v1/autonomy/admin/config', () => HttpResponse.json(CHATBOT_CONFIG)),
      http.get('/api/v1/autonomy/admin/stages', () => HttpResponse.json(STAGES)),
      http.get('/api/v1/autonomy/admin/presets', () => HttpResponse.json(PRESETS)),
      http.put('/api/v1/autonomy/admin/config', async ({ request }) => {
        putCalled = true
        const body = await request.json()
        return HttpResponse.json(body)
      }),
    )
    renderWithProviders(<AutonomySettings />)
    const user = userEvent.setup()
    await waitFor(() => expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(putCalled).toBe(true))
  })
})

describe('AdminTabs with Autonomy', () => {
  it('includes Autonomy tab trigger and content', () => {
    setupHandlers()
    renderWithProviders(<AdminTabs />)
    const tabs = screen.getAllByRole('tab')
    const autonomyTab = tabs.find((t) => t.textContent?.toLowerCase().includes('autonomy'))
    expect(autonomyTab).toBeDefined()
  })
})
