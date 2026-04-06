import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { ExportMenu } from './ExportMenu'

describe('ExportMenu', () => {
  it('renders export button', () => {
    renderWithProviders(<ExportMenu outputId="o1" />)
    expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument()
  })

  it('opens dropdown with 3 format options', async () => {
    renderWithProviders(<ExportMenu outputId="o1" />)
    await userEvent.click(screen.getByRole('button', { name: /export/i }))
    expect(screen.getByRole('menuitem', { name: /pdf/i })).toBeInTheDocument()
    expect(
      screen.getByRole('menuitem', { name: /docx/i })
    ).toBeInTheDocument()
    expect(
      screen.getByRole('menuitem', { name: /json/i })
    ).toBeInTheDocument()
  })
})
