import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/msw/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { PracticeAreaChips } from './PracticeAreaChips'
import type { PracticeArea } from '../types'

const PI: PracticeArea = {
  id: 'personal_injury',
  display_name: 'Personal Injury',
  welcome_message_consumer: 'Tell me about your accident.',
  welcome_message_professional: 'Capture the incident facts.',
  disclaimer: null,
}

const FAMILY: PracticeArea = {
  id: 'family_law',
  display_name: 'Family Law',
  welcome_message_consumer: 'Tell me about your family situation.',
  welcome_message_professional: 'Family law intake.',
  disclaimer: 'Sensitive matters: please call 988 if in crisis.',
}

function mockPracticeAreas(areas: PracticeArea[] = [PI, FAMILY]) {
  server.use(
    http.get('/api/practice-areas', () =>
      HttpResponse.json({ practice_areas: areas }),
    ),
  )
}

function Wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
    },
  })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('PracticeAreaChips', () => {
  beforeEach(() => {
    mockPracticeAreas()
  })

  it('renders the Generic chip plus a chip per practice area', async () => {
    const onSelect = vi.fn()
    render(<PracticeAreaChips selectedId={null} onSelect={onSelect} />, {
      wrapper: Wrapper,
    })
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: 'Generic' })).toBeInTheDocument(),
    )
    expect(
      screen.getByRole('radio', { name: 'Personal Injury' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('radio', { name: 'Family Law' }),
    ).toBeInTheDocument()
    // Generic is checked when selectedId is null
    expect(screen.getByRole('radio', { name: 'Generic' })).toHaveAttribute(
      'aria-checked',
      'true',
    )
  })

  it('clicking a practice chip fires onSelect with that practice id', async () => {
    const onSelect = vi.fn()
    render(<PracticeAreaChips selectedId={null} onSelect={onSelect} />, {
      wrapper: Wrapper,
    })
    const piChip = await screen.findByRole('radio', { name: 'Personal Injury' })
    await userEvent.click(piChip)
    expect(onSelect).toHaveBeenCalledWith('personal_injury')
  })

  it('clicking the Generic chip fires onSelect(null)', async () => {
    const onSelect = vi.fn()
    render(
      <PracticeAreaChips selectedId="personal_injury" onSelect={onSelect} />,
      { wrapper: Wrapper },
    )
    const genericChip = await screen.findByRole('radio', { name: 'Generic' })
    await userEvent.click(genericChip)
    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it('renders disclaimer only when the selected practice has one', async () => {
    const onSelect = vi.fn()
    const { rerender } = render(
      <PracticeAreaChips selectedId={null} onSelect={onSelect} />,
      { wrapper: Wrapper },
    )
    await screen.findByRole('radio', { name: 'Generic' })
    expect(screen.queryByRole('note')).not.toBeInTheDocument()

    // Family Law has a disclaimer
    rerender(
      <PracticeAreaChips selectedId="family_law" onSelect={onSelect} />,
    )
    expect(await screen.findByRole('note')).toHaveTextContent(/988/)

    // Personal Injury does not — disclaimer should disappear
    rerender(
      <PracticeAreaChips selectedId="personal_injury" onSelect={onSelect} />,
    )
    await waitFor(() => expect(screen.queryByRole('note')).not.toBeInTheDocument())
  })

  it('arrow keys move focus and select the next chip', async () => {
    const onSelect = vi.fn()
    render(<PracticeAreaChips selectedId={null} onSelect={onSelect} />, {
      wrapper: Wrapper,
    })
    const generic = await screen.findByRole('radio', { name: 'Generic' })
    generic.focus()
    expect(generic).toHaveFocus()

    await userEvent.keyboard('{ArrowRight}')
    // Practice areas are sorted by display_name -> Family Law, Personal Injury
    // After Generic, the next chip is Family Law.
    expect(onSelect).toHaveBeenLastCalledWith('family_law')
  })

  it('Enter on a focused chip selects it', async () => {
    const onSelect = vi.fn()
    render(<PracticeAreaChips selectedId={null} onSelect={onSelect} />, {
      wrapper: Wrapper,
    })
    const piChip = await screen.findByRole('radio', { name: 'Personal Injury' })
    piChip.focus()
    await userEvent.keyboard('{Enter}')
    expect(onSelect).toHaveBeenCalledWith('personal_injury')
  })

  it('renders nothing when the API errors out', async () => {
    server.use(
      http.get('/api/practice-areas', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    const onSelect = vi.fn()
    const { container } = render(
      <PracticeAreaChips selectedId={null} onSelect={onSelect} />,
      { wrapper: Wrapper },
    )
    await waitFor(() =>
      expect(container.querySelector('[role="radiogroup"]')).toBeNull(),
    )
  })
})
