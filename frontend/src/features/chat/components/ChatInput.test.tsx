import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { ChatInput } from './ChatInput'

// Mock wavesurfer for VoiceRecorder (rendered on voice modality)
const mockRecordPlugin = {
  startRecording: vi.fn(() => Promise.resolve()),
  stopRecording: vi.fn(),
  destroy: vi.fn(),
  on: vi.fn(),
}
vi.mock('@wavesurfer/react', () => ({
  useWavesurfer: () => ({ wavesurfer: { registerPlugin: () => mockRecordPlugin } }),
}))
vi.mock('wavesurfer.js/dist/plugins/record.esm.js', () => ({
  default: { create: () => mockRecordPlugin },
}))

describe('ChatInput', () => {
  it('renders textarea and 3 modality buttons + send button', () => {
    renderWithProviders(<ChatInput onSend={() => {}} />)
    expect(screen.getByRole('radio', { name: /text/i })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /voice/i })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /document/i })).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument()
  })

  it('text modality is active by default', () => {
    renderWithProviders(<ChatInput onSend={() => {}} />)
    expect(screen.getByRole('radio', { name: /text/i })).toHaveAttribute(
      'aria-checked',
      'true',
    )
  })

  it('switches active modality on click', async () => {
    renderWithProviders(<ChatInput onSend={() => {}} />)
    await userEvent.click(screen.getByRole('radio', { name: /voice/i }))
    expect(screen.getByRole('radio', { name: /voice/i })).toHaveAttribute(
      'aria-checked',
      'true',
    )
    expect(screen.getByRole('radio', { name: /text/i })).toHaveAttribute(
      'aria-checked',
      'false',
    )
  })

  it('calls onSend with modality + content on Enter', async () => {
    const onSend = vi.fn()
    renderWithProviders(<ChatInput onSend={onSend} />)
    await userEvent.type(screen.getByRole('textbox'), 'hello{Enter}')
    expect(onSend).toHaveBeenCalledWith({ modality: 'text', content: 'hello' })
  })

  it('Shift+Enter inserts newline', async () => {
    const onSend = vi.fn()
    renderWithProviders(<ChatInput onSend={onSend} />)
    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'line1{Shift>}{Enter}{/Shift}line2')
    expect(onSend).not.toHaveBeenCalled()
    expect(textarea).toHaveValue('line1\nline2')
  })

  it('icon-only modality buttons have aria-label', () => {
    renderWithProviders(<ChatInput onSend={() => {}} />)
    const radios = screen.getAllByRole('radio')
    for (const radio of radios) {
      expect(radio).toHaveAttribute('aria-label')
      expect(radio.getAttribute('aria-label')).not.toBe('')
    }
  })

  // Task 05-04: VoiceRecorder/DocumentUploader wiring tests
  it('clicking mic button renders VoiceRecorder component', async () => {
    renderWithProviders(<ChatInput onSend={() => {}} />)
    await userEvent.click(screen.getByRole('radio', { name: /voice/i }))
    expect(screen.getByTestId('voice-recorder-surface')).toBeInTheDocument()
    // Textarea should be hidden in voice mode
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('clicking paperclip button renders DocumentUploader component', async () => {
    renderWithProviders(<ChatInput onSend={() => {}} />)
    await userEvent.click(screen.getByRole('radio', { name: /document/i }))
    expect(screen.getByTestId('document-uploader-surface')).toBeInTheDocument()
    // Textarea should be hidden in document mode
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('clicking voice cancel returns to text modality', async () => {
    renderWithProviders(<ChatInput onSend={() => {}} />)
    await userEvent.click(screen.getByRole('radio', { name: /voice/i }))
    expect(screen.getByTestId('voice-recorder-surface')).toBeInTheDocument()
    // Click the cancel button inside VoiceRecorder
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    // Should return to text mode
    expect(screen.queryByTestId('voice-recorder-surface')).not.toBeInTheDocument()
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('clicking document cancel returns to text modality', async () => {
    renderWithProviders(<ChatInput onSend={() => {}} />)
    await userEvent.click(screen.getByRole('radio', { name: /document/i }))
    expect(screen.getByTestId('document-uploader-surface')).toBeInTheDocument()
    // Click the cancel button inside DocumentUploader
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    // Should return to text mode
    expect(screen.queryByTestId('document-uploader-surface')).not.toBeInTheDocument()
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('clicking text modality from voice mode returns to textarea', async () => {
    renderWithProviders(<ChatInput onSend={() => {}} />)
    await userEvent.click(screen.getByRole('radio', { name: /voice/i }))
    expect(screen.getByTestId('voice-recorder-surface')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('radio', { name: /text/i }))
    expect(screen.queryByTestId('voice-recorder-surface')).not.toBeInTheDocument()
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })
})
