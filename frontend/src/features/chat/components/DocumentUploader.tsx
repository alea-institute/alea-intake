import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { FileText, X } from 'lucide-react'

interface Props {
  onFileSelected: (file: File) => void
  onCancel: () => void
  maxSizeMB?: number
}

const ALLOWED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'image/jpeg', 'image/png', 'image/tiff',
]

export function DocumentUploader({ onFileSelected, onCancel, maxSizeMB = 25 }: Props) {
  const { t } = useTranslation(['chat', 'common'])
  const inputRef = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setError(null)
    if (!ALLOWED_TYPES.includes(file.type)) {
      setError(t('common:errors.fileTypeUnsupported'))
      return
    }
    const sizeMB = file.size / (1024 * 1024)
    if (sizeMB > maxSizeMB) {
      setError(t('common:errors.fileTooLarge', { size: sizeMB.toFixed(1), limit: maxSizeMB }))
      return
    }
    onFileSelected(file)
  }

  return (
    <div className="bg-card rounded-md p-md border border-border space-y-md">
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.jpg,.jpeg,.png,.tiff"
        onChange={handleSelect}
        className="sr-only"
        aria-label={t('common:cta.uploadDocument')}
      />
      <div className="flex items-center gap-md">
        <Button type="button" onClick={() => inputRef.current?.click()} className="min-h-[44px]">
          <FileText className="h-4 w-4 mr-xs" aria-hidden="true" />
          {t('common:cta.uploadDocument')}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel} className="min-h-[44px] min-w-[44px]" aria-label={t('chat:voice.cancel', 'Cancel')}>
          <X className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
      {error && <p role="alert" className="text-[14px] text-destructive">{error}</p>}
      <p className="text-[14px] text-muted-foreground">
        {t('chat:document.hint', 'Accepted: PDF, DOCX, JPG, PNG, TIFF — up to {{limit}}MB', { limit: maxSizeMB })}
      </p>
    </div>
  )
}
