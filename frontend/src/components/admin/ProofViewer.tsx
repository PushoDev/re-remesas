import { useQuery } from '@tanstack/react-query'
import { Download, FileText, Loader2 } from 'lucide-react'
import { useEffect, useMemo } from 'react'
import { parseApiError } from '../../lib/apiErrors'
import { fetchProof } from '../../services/adminRemittanceService'

/** Shows the proof file. It is fetched with the administrator's token and shown from memory: the file has no URL of its own. */
export default function ProofViewer({ trackingId }: { trackingId: string }) {
  const { data: blob, isPending, isError, error } = useQuery({
    queryKey: ['admin', 'proof', trackingId],
    queryFn: () => fetchProof(trackingId),
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  })

  const url = useMemo(() => (blob ? URL.createObjectURL(blob) : null), [blob])
  useEffect(() => () => { if (url) URL.revokeObjectURL(url) }, [url])

  if (isPending) {
    return <p role="status" className="flex items-center gap-2 text-sm text-slate-600"><Loader2 className="size-4 animate-spin" aria-hidden /> Cargando comprobante…</p>
  }
  if (isError || !blob || !url) {
    return <p role="alert" className="text-sm text-red-600">No se pudo cargar el comprobante. {isError ? parseApiError(error).message : ''}</p>
  }

  const isImage = blob.type.startsWith('image/')
  return (
    <div className="space-y-3">
      {isImage ? (
        <img src={url} alt="Comprobante de pago enviado por el cliente" className="max-h-[60dvh] w-full rounded-lg border border-slate-200 object-contain" />
      ) : (
        <object data={url} type={blob.type} aria-label="Comprobante de pago en PDF" className="h-[60dvh] w-full rounded-lg border border-slate-200">
          <p className="flex items-center gap-2 p-4 text-sm text-slate-600"><FileText className="size-4" aria-hidden /> Tu navegador no puede mostrar el PDF aquí.</p>
        </object>
      )}
      <a
        href={url}
        download={`comprobante-${trackingId}.${blob.type === 'application/pdf' ? 'pdf' : blob.type.split('/')[1] ?? 'bin'}`}
        className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
      >
        <Download className="size-4" aria-hidden /> Descargar
      </a>
    </div>
  )
}
