import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/features/auth/store'
import { fetchOrg, updateOrg } from '../api'

const schema = z.object({
  name: z.string().min(2).max(100),
  accent_color: z
    .string()
    .regex(/^#[0-9A-Fa-f]{6}$/, 'Must be a hex color like #1E3A5F')
    .optional()
    .or(z.literal('')),
  logo_url: z.string().url().optional().or(z.literal('')),
})

type FormData = z.infer<typeof schema>

export function OrgProfileForm() {
  const { t } = useTranslation('admin')
  const user = useAuth((s) => s.user)
  const orgId = user?.org_id ?? ''
  const qc = useQueryClient()
  const { data: org } = useQuery({
    queryKey: ['org', orgId],
    queryFn: () => fetchOrg(orgId),
    enabled: !!orgId,
  })

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    values: org
      ? {
          name: org.name,
          accent_color: org.accent_color ?? '',
          logo_url: org.logo_url ?? '',
        }
      : undefined,
  })

  const mutation = useMutation({
    mutationFn: (patch: FormData) => updateOrg(orgId, patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['org', orgId] })
      toast.success(t('org.saved', 'Organization saved'))
    },
    onError: () => toast.error(t('org.saveError', 'Failed to save organization')),
  })

  return (
    <form
      onSubmit={handleSubmit((d) => mutation.mutate(d))}
      className="space-y-[16px] max-w-md"
    >
      <div className="space-y-[8px]">
        <label
          htmlFor="org-name"
          className="block font-body text-[14px] font-medium"
        >
          {t('org.nameLabel', 'Organization name')}
        </label>
        <Input
          id="org-name"
          {...register('name')}
          className="min-h-[44px]"
          aria-invalid={!!errors.name}
        />
        {errors.name && (
          <p role="alert" className="text-[14px] text-destructive">
            {errors.name.message}
          </p>
        )}
      </div>
      <div className="space-y-[8px]">
        <label
          htmlFor="org-accent"
          className="block font-body text-[14px] font-medium"
        >
          {t('org.accentLabel', 'Accent color (optional)')}
        </label>
        <Input
          id="org-accent"
          {...register('accent_color')}
          placeholder="#1E3A5F"
          className="min-h-[44px]"
          aria-invalid={!!errors.accent_color}
        />
        {errors.accent_color && (
          <p role="alert" className="text-[14px] text-destructive">
            {errors.accent_color.message}
          </p>
        )}
      </div>
      <div className="space-y-[8px]">
        <label
          htmlFor="org-logo"
          className="block font-body text-[14px] font-medium"
        >
          {t('org.logoLabel', 'Logo URL (optional)')}
        </label>
        <Input
          id="org-logo"
          {...register('logo_url')}
          placeholder="https://..."
          className="min-h-[44px]"
          aria-invalid={!!errors.logo_url}
        />
        {errors.logo_url && (
          <p role="alert" className="text-[14px] text-destructive">
            {errors.logo_url.message}
          </p>
        )}
      </div>
      <Button type="submit" disabled={isSubmitting} className="min-h-[44px]">
        {isSubmitting
          ? t('org.saving', 'Saving...')
          : t('org.save', 'Save changes')}
      </Button>
    </form>
  )
}
