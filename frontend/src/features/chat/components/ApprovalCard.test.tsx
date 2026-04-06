import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/msw/server'
import { renderWithProviders } from '@/test/utils'
import { ApprovalCard } from './ApprovalCard'
import type { ApprovalRequest } from '@/features/autonomy/types'

const mockRequest: ApprovalRequest = {
  id: 42,
  run_id: 1,
  iteration_id: 1,
  stage_name: 'issue_spot',
  status: 'pending',
  safety_triggered: false,
  is_rerun: false,
  rerun_attempt: 0,
  guidance_text: null,
  stage_output_json: { issues: ['custody', 'dv'] },
  created_at: '2026-04-01T00:00:00Z',
  resolved_at: null,
}

const safetyRequest: ApprovalRequest = {
  ...mockRequest,
  safety_triggered: true,
}

describe('ApprovalCard', () => {
  it('renders stage name and Approve/Reject/Edit buttons', () => {
    renderWithProviders(<ApprovalCard request={mockRequest} onAction={() => {}} />)
    expect(screen.getByText(/issue spotting/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument()
  })

  it('Approve button calls approveStage API', async () => {
    let approveCalled = false
    server.use(
      http.post('/api/v1/autonomy/requests/42/approve', () => {
        approveCalled = true
        return HttpResponse.json({ status: 'approved' })
      }),
    )
    const onAction = vi.fn()
    renderWithProviders(<ApprovalCard request={mockRequest} onAction={onAction} />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /approve/i }))
    await waitFor(() => expect(approveCalled).toBe(true))
    await waitFor(() => expect(onAction).toHaveBeenCalled())
  })

  it('Reject button shows guidance text input, then calls rejectStage API', async () => {
    let rejectCalled = false
    server.use(
      http.post('/api/v1/autonomy/requests/42/reject', async ({ request }) => {
        rejectCalled = true
        const body = await request.json() as Record<string, unknown>
        expect(body.guidance_text).toBe('Please reconsider')
        return HttpResponse.json({ status: 'rejected' })
      }),
    )
    const onAction = vi.fn()
    renderWithProviders(<ApprovalCard request={mockRequest} onAction={onAction} />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /reject/i }))
    // Guidance textarea should appear
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/guidance/i)).toBeInTheDocument()
    })
    await user.type(screen.getByPlaceholderText(/guidance/i), 'Please reconsider')
    await user.click(screen.getByRole('button', { name: /submit rejection/i }))
    await waitFor(() => expect(rejectCalled).toBe(true))
    await waitFor(() => expect(onAction).toHaveBeenCalled())
  })

  it('Edit button shows editable output, then calls editStage API', async () => {
    let editCalled = false
    server.use(
      http.post('/api/v1/autonomy/requests/42/edit', async () => {
        editCalled = true
        return HttpResponse.json({ status: 'edited' })
      }),
    )
    const onAction = vi.fn()
    renderWithProviders(<ApprovalCard request={mockRequest} onAction={onAction} />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /edit/i }))
    // Editable textarea should appear with JSON content
    await waitFor(() => {
      expect(screen.getByRole('textbox')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /save edits/i }))
    await waitFor(() => expect(editCalled).toBe(true))
    await waitFor(() => expect(onAction).toHaveBeenCalled())
  })

  it('shows safety badge when safety_triggered=true', () => {
    renderWithProviders(<ApprovalCard request={safetyRequest} onAction={() => {}} />)
    expect(screen.getByText(/safety alert/i)).toBeInTheDocument()
  })
})
