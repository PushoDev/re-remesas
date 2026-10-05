import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BadgeCheck, Loader2, PackageCheck, XCircle } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { ACTION_LABEL, validateCancelReason, visibleActions, type AdminAction } from '../../lib/adminRemittances'
import { parseApiError } from '../../lib/apiErrors'
import { inputClass } from '../../lib/formStyles'
import { changeRemittanceStatus } from '../../services/adminRemittanceService'
import type { AdminRemittanceDetail } from '../../types/adminRemittances'
import ErrorAlert from '../ErrorAlert'
import Modal from '../Modal'

const ICON: Record<AdminAction, ReactNode> = {
  confirm_payment: <BadgeCheck className="size-5" aria-hidden />,
  complete: <PackageCheck className="size-5" aria-hidden />,
  cancel: <XCircle className="size-5" aria-hidden />,
}
const STYLE: Record<AdminAction, string> = {
  confirm_payment: 'bg-emerald-600 text-white hover:bg-emerald-700',
  complete: 'bg-blue-700 text-white hover:bg-blue-800',
  cancel: 'border border-red-300 bg-white text-red-700 hover:bg-red-50',
}
const TARGET = { confirm_payment: 'PAID', complete: 'COMPLETED', cancel: 'CANCELLED' } as const

const COPY: Record<AdminAction, { title: string; text: string; confirm: string }> = {
  confirm_payment: {
    title: '¿Confirmar el pago?',
    text: 'Confirma que revisaste el comprobante y que el dinero llegó. La remesa pasará a «Pagado» y quedará registrado que lo verificaste tú.',
    confirm: 'Sí, confirmar pago',
  },
  complete: {
    title: '¿Marcar como entregada?',
    text: 'Confirma que el dinero ya se entregó al destinatario en Cuba. No se podrá deshacer.',
    confirm: 'Sí, marcar entregada',
  },
  cancel: {
    title: '¿Cancelar la remesa?',
    text: 'No se podrá deshacer. Si ya estaba pagada, el reembolso al cliente es manual.',
    confirm: 'Sí, cancelar',
  },
}

export default function RemittanceActions({ remittance }: { remittance: AdminRemittanceDetail }) {
  const queryClient = useQueryClient()
  const [action, setAction] = useState<AdminAction | null>(null)
  const [note, setNote] = useState('')
  const [reasonError, setReasonError] = useState<string | null>(null)

  const actions = visibleActions(remittance.allowed_actions)

  const close = () => {
    setAction(null)
    setNote('')
    setReasonError(null)
    mutation.reset()
  }

  const mutation = useMutation({
    mutationFn: (chosen: AdminAction) =>
      changeRemittanceStatus(remittance.tracking_id, { status: TARGET[chosen], note: note.trim() }),
    onSuccess: async (updated) => {
      queryClient.setQueryData(['admin', 'remittance', remittance.tracking_id], updated)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['admin', 'remittances'] }),
        queryClient.invalidateQueries({ queryKey: ['admin', 'overview'] }),
        queryClient.invalidateQueries({ queryKey: ['remittance'] }),
      ])
      toast.success(`Listo: ahora está «${updated.status_display}».`)
      close()
    },
  })

  if (actions.length === 0) {
    return <p className="text-sm text-slate-500">Esta remesa ya terminó: no admite más acciones.</p>
  }

  const submit = () => {
    if (!action) return
    if (action === 'cancel') {
      const problem = validateCancelReason(note)
      setReasonError(problem)
      if (problem) return
    }
    mutation.mutate(action)
  }
  const serverError = mutation.error ? parseApiError(mutation.error) : null
  const serverMessage = serverError ? (serverError.fieldErrors.status?.[0] ?? serverError.fieldErrors.note?.[0] ?? serverError.message) : null

  return (
    <>
      <div className="flex flex-wrap gap-3">
        {actions.map((candidate) => (
          <button
            key={candidate}
            type="button"
            onClick={() => setAction(candidate)}
            className={`inline-flex items-center gap-2 rounded-lg px-4 py-2.5 font-semibold shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 ${STYLE[candidate]}`}
          >
            {ICON[candidate]}
            {ACTION_LABEL[candidate]}
          </button>
        ))}
      </div>

      <Modal open={action !== null} onClose={close} title={action ? COPY[action].title : ''}>
        {action && (
          <div className="space-y-4">
            <p className="text-slate-700">{COPY[action].text}</p>
            {serverMessage && <ErrorAlert message={serverMessage} />}

            {action !== 'confirm_payment' && (
              <div>
                <label htmlFor="status-note" className="text-sm font-medium text-slate-700">
                  {action === 'cancel' ? 'Motivo (obligatorio)' : 'Nota (opcional)'}
                </label>
                <textarea
                  id="status-note"
                  rows={3}
                  maxLength={500}
                  value={note}
                  onChange={(event) => { setNote(event.target.value); setReasonError(null) }}
                  aria-invalid={reasonError ? 'true' : 'false'}
                  aria-describedby={reasonError ? 'status-note-error' : undefined}
                  className={inputClass}
                  placeholder={action === 'cancel' ? 'Por ejemplo: el comprobante no corresponde al monto.' : 'Por ejemplo: entregado en mano a la hermana.'}
                />
                {reasonError && <p id="status-note-error" className="mt-1 text-sm text-red-600">{reasonError}</p>}
              </div>
            )}

            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button type="button" onClick={close} disabled={mutation.isPending} className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60">
                Volver
              </button>
              <button
                type="button"
                onClick={submit}
                disabled={mutation.isPending}
                className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 font-semibold disabled:opacity-70 ${action === 'cancel' ? 'bg-red-600 text-white hover:bg-red-700' : STYLE[action]}`}
              >
                {mutation.isPending && <Loader2 className="size-5 animate-spin" aria-hidden />}
                {COPY[action].confirm}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </>
  )
}
