import { useMutation, useQueryClient } from '@tanstack/react-query'
import { FileCheck2, Loader2, Upload } from 'lucide-react'
import { useId, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { toast } from 'sonner'
import { parseApiError } from '../../lib/apiErrors'
import { inputClass, primaryButtonClass } from '../../lib/formStyles'
import { ACCEPTED_EXTENSIONS, formatFileSize, validateProofFile } from '../../lib/proofFile'
import { submitPaymentProof } from '../../services/remittanceService'
import type { RemittanceDetail } from '../../types/remittances'
import ErrorAlert from '../ErrorAlert'

/** For manual payments (Zelle, Wise, cash): the customer says how they paid so an administrator can verify it. */
export default function PaymentProofForm({ remittance }: { remittance: RemittanceDetail }) {
  const queryClient = useQueryClient()
  const inputId = useId()
  const fileInput = useRef<HTMLInputElement>(null)
  const [reference, setReference] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [emptyError, setEmptyError] = useState(false)

  const mutation = useMutation({
    mutationFn: () => submitPaymentProof(remittance.tracking_id, { reference, file }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['remittance', remittance.tracking_id], updated)
      toast.success('Comprobante enviado. Un administrador lo revisará.')
      setReference('')
      setFile(null)
      if (fileInput.current) fileInput.current.value = ''
    },
  })

  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0] ?? null
    setEmptyError(false)
    if (!chosen) {
      setFile(null)
      setFileError(null)
      return
    }
    const problem = await validateProofFile(chosen)
    setFileError(problem)
    setFile(problem ? null : chosen)
    if (problem && fileInput.current) fileInput.current.value = ''
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!reference.trim() && !file) {
      setEmptyError(true)
      return
    }
    setEmptyError(false)
    mutation.mutate()
  }

  const serverError = mutation.error ? parseApiError(mutation.error) : null
  const serverMessage = serverError
    ? (serverError.fieldErrors.file?.[0] ?? serverError.fieldErrors.reference?.[0] ?? serverError.fieldErrors.non_field_errors?.[0] ?? serverError.message)
    : null
  const alreadySent = Boolean(remittance.payment_reference) || remittance.has_proof_file

  return (
    <form onSubmit={onSubmit} noValidate className="mt-4 space-y-3 border-t border-slate-100 pt-4">
      <h3 className="text-sm font-semibold text-slate-900">Envía tu comprobante</h3>

      {alreadySent && (
        <p className="flex items-start gap-2 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900">
          <FileCheck2 className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            Ya enviaste {remittance.payment_reference && <>la referencia <strong>{remittance.payment_reference}</strong></>}
            {remittance.payment_reference && remittance.has_proof_file && ' y '}
            {remittance.has_proof_file && 'un archivo'}. Puedes enviar otro para reemplazarlo.
          </span>
        </p>
      )}
      {serverMessage && <ErrorAlert message={serverMessage} />}
      {emptyError && <ErrorAlert message="Escribe la referencia del pago o adjunta el comprobante." />}

      <div>
        <label htmlFor={`${inputId}-ref`} className="text-sm font-medium text-slate-700">Referencia del pago <span className="font-normal text-slate-400">(opcional)</span></label>
        <input id={`${inputId}-ref`} value={reference} maxLength={120} onChange={(event) => { setReference(event.target.value); setEmptyError(false) }}
          placeholder="Número de confirmación o de operación" autoComplete="off" className={inputClass} />
      </div>

      <div>
        <label htmlFor={inputId} className="text-sm font-medium text-slate-700">Foto o PDF del comprobante <span className="font-normal text-slate-400">(opcional)</span></label>
        <input ref={fileInput} id={inputId} type="file" accept={ACCEPTED_EXTENSIONS.join(',')} onChange={(event) => void onFile(event)}
          aria-invalid={fileError ? 'true' : 'false'} aria-describedby={`${inputId}-hint`}
          className="mt-1 block w-full text-sm text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-2 file:font-medium file:text-blue-700 hover:file:bg-blue-100" />
        <p id={`${inputId}-hint`} className="mt-1 text-xs text-slate-500">
          {file ? `${file.name} · ${formatFileSize(file.size)}` : 'JPG, PNG o PDF, hasta 5 MB.'}
        </p>
        {fileError && <p role="alert" className="mt-1 text-sm text-red-600">{fileError}</p>}
      </div>

      <button type="submit" disabled={mutation.isPending} className={`${primaryButtonClass} sm:w-auto`}>
        {mutation.isPending ? <Loader2 className="size-5 animate-spin" aria-hidden /> : <Upload className="size-5" aria-hidden />}
        {alreadySent ? 'Reemplazar comprobante' : 'Enviar comprobante'}
      </button>
    </form>
  )
}
