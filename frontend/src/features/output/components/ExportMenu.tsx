import { useState } from 'react'
import { Download } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { exportOutput } from '../api'

interface Props {
  outputId: string
}

export function ExportMenu({ outputId }: Props) {
  const { t } = useTranslation(['output', 'common'])
  const [exporting, setExporting] = useState<string | null>(null)

  const handleExport = async (format: 'pdf' | 'docx' | 'json') => {
    setExporting(format)
    try {
      toast.info(
        t('output:preparing', 'Preparing your {{format}} export...', {
          format: format.toUpperCase(),
        })
      )
      await exportOutput(outputId, format)
    } catch {
      toast.error(t('common:errors.exportFailed'))
    } finally {
      setExporting(null)
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button className="min-h-[44px]" disabled={exporting !== null}>
          <Download className="h-4 w-4 mr-[4px]" aria-hidden="true" />
          {t('common:cta.exportIntake')}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          onClick={() => handleExport('pdf')}
          className="min-h-[44px] cursor-pointer"
        >
          {t('output:format.pdf', 'PDF')}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => handleExport('docx')}
          className="min-h-[44px] cursor-pointer"
        >
          {t('output:format.docx', 'Word (DOCX)')}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => handleExport('json')}
          className="min-h-[44px] cursor-pointer"
        >
          {t('output:format.json', 'JSON')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
