import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'

// Mock wavesurfer hook + plugin
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

import { VoiceRecorder } from './VoiceRecorder'

describe('VoiceRecorder', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders microphone button + timer + waveform', () => {
    renderWithProviders(<VoiceRecorder onRecorded={() => {}} onCancel={() => {}} />)
    expect(screen.getByRole('button', { name: /startRecording|start recording/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
    expect(screen.getByText(/0:00/)).toBeInTheDocument()
  })

  it('starts recording on button click', async () => {
    renderWithProviders(<VoiceRecorder onRecorded={() => {}} onCancel={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /startRecording|start recording/i }))
    expect(mockRecordPlugin.startRecording).toHaveBeenCalled()
  })

  it('calls onCancel on cancel click', async () => {
    const onCancel = vi.fn()
    renderWithProviders(<VoiceRecorder onRecorded={() => {}} onCancel={onCancel} />)
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onCancel).toHaveBeenCalled()
  })

  it('microphone button has min 44px touch target', () => {
    renderWithProviders(<VoiceRecorder onRecorded={() => {}} onCancel={() => {}} />)
    const btn = screen.getByRole('button', { name: /startRecording|start recording/i })
    expect(btn.className).toMatch(/min-h-\[44px\]/)
    expect(btn.className).toMatch(/min-w-\[44px\]/)
  })
})
