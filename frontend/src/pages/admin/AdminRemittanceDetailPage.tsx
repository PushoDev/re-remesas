import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, BadgeCheck, FileSearch, Loader2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import CopyButton from '../../components/CopyButton'
import Modal from '../../components/Modal'
import Money from '../../components/Money'
import ProofViewer from '../../components/admin/ProofViewer'
import RemittanceActions from '../../components/admin/RemittanceActions'
import StatusBadge from '../../components/remittances/StatusBadge'
import Timeline, { type TimelineItem } from '../../components/Timeline'
import { parseApiError } from '../../lib/apiErrors'
import { formatDecimal } from '../../lib/decimal'
import { getAdminRemittance } from '../../services/adminRemittanceService'
import type { AdminStatusLogEntry } from '../../types/adminRemittances'

const dateTime = new Intl.DateTimeFormat('es', { dateStyle: 'long', timeStyle: 'short' })

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-base font-semibold text-slate-900">{title}</h2>
      {children}
    </section>
  )
}

function Fields({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-slate-600">{label}</dt>
          <dd className="break-words text-right text-slate-900 sm:text-left">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function toTimeline(entries: AdminStatusLogEntry[]): TimelineItem[] {
  return entries.map((entry, index) => {
    const change = entry.from_status !== entry.to_status
    return {
      key: index,
      title: !entry.from_status ? 'Solicitud creada' : change ? `${entry.from_status_display} → ${entry.to_status_display}` : 'Anotación',
      at: entry.changed_at,
      meta: `${entry.source_display}${entry.changed_by_email ? ` · ${entry.changed_by_email}` : ''}`,
      note: entry.note || undefined,
      event: change,
      tone: entry.to_status === 'CANCELLED' ? 'danger' : entry.to_status === 'COMPLETED' ? 'success' : entry.to_status === 'PAID' ? 'default' : 'warning',
    }
  })
}

export default function AdminRemittanceDetailPage() {
  const { trackingId = '' } = useParams()
  const [showProof, setShowProof] = useState(false)

  const { data: r, isPending, isError, error } = useQuery({
    queryKey: ['admin', 'remittance', trackingId],
    queryFn: () => getAdminRemittance(trackingId),
    retry: false,
  })

  if (isPending) {
    return <p role="status" className="flex items-center gap-2 text-slate-600"><Loader2 className="size-5 animate-spin" aria-hidden /> Cargando la remesa…</p>
  }
  if (isError || !r) {
    return (
      <div role="alert" className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">No encontramos esa remesa</h2>
        <p className="mt-1 text-slate-600">{isError ? parseApiError(error).message : ''}</p>
        <Link to="/admin/remittances" className="mt-3 inline-block font-semibold text-blue-700 hover:underline">Volver a la bandeja</Link>
      </div>
    )
  }

  const cash = r.delivery_method === 'CASH_DELIVERY'
  const manual = r.payment.provider === 'MANUAL'
  const hasProof = r.has_proof_file || Boolean(r.payment_reference)

  return (
    <div className="space-y-5">
      <Link to="/admin/remittances" className="inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:underline">
        <ArrowLeft className="size-4" aria-hidden /> Volver a la bandeja
      </Link>

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-600">ID de seguimiento</p>
          <p className="mt-1 flex flex-wrap items-center gap-3">
            <span className="font-mono text-2xl font-bold tracking-wide text-slate-900">{r.tracking_id}</span>
            <CopyButton text={r.tracking_id} />
          </p>
          <p className="mt-1 text-sm text-slate-500">Creada el {dateTime.format(new Date(r.created_at))}</p>
        </div>
        <StatusBadge status={r.status} label={r.status_display} />
      </header>

      <section aria-label="Acciones" className="rounded-2xl border border-blue-100 bg-blue-50/60 p-4">
        <RemittanceActions remittance={r} />
      </section>

      <div className="grid gap-5 md:grid-cols-2">
        <Panel title="Remitente">
          <Fields rows={[
            ['Correo', r.sender.email],
            ['Nombre', [r.sender.first_name, r.sender.last_name].filter(Boolean).join(' ') || '—'],
            ['Membresía', r.sender.membership_status === 'VIP' ? <span key="vip" className="inline-flex items-center gap-1 font-medium text-amber-700"><BadgeCheck className="size-4" aria-hidden /> VIP</span> : 'Gratuita'],
          ]} />
        </Panel>

        <Panel title="Destinatario y entrega">
          <Fields rows={[
            ['Nombre', r.recipient_name],
            ['Teléfono', r.recipient_phone],
            ['Entrega', r.delivery_method_display],
            [cash ? 'Dirección' : 'Cuenta', cash ? r.recipient_address : r.recipient_account],
          ]} />
        </Panel>

        <Panel title="El dinero (fijado al crear)">
          <Fields rows={[
            ['Enviado', <Money key="a" amount={r.amount_sent} currency={r.currency} className="font-semibold" />],
            ['Tasa de cambio', `1 ${r.currency} = ${formatDecimal(r.base_rate_used)} CUP`],
            ['Margen', `${formatDecimal(r.spread_percent_used)} %${r.is_vip_rate ? ' (tarifa VIP)' : ''}`],
            ['Tasa aplicada', `1 ${r.currency} = ${formatDecimal(r.effective_rate_used)} CUP`],
            ['Debe recibir', <Money key="b" amount={r.amount_cup} currency="CUP" className="text-base font-bold" />],
          ]} />
        </Panel>

        <Panel title="Pago">
          <Fields rows={[
            ['Medio', `${r.payment_method_display} · ${manual ? 'manual' : 'en línea (simulado)'}`],
            ['Estado del pago', { PENDING: 'Pendiente', SUCCEEDED: 'Pagado', FAILED: 'Fallido' }[r.payment.status]],
            ['Importe', <Money key="p" amount={r.payment.amount} currency={r.payment.currency} />],
            ['Confirmado por', r.payment.confirmed_by_email ?? (r.payment.status === 'SUCCEEDED' ? 'La pasarela' : '—')],
            ['Referencia del cliente', r.payment_reference || '—'],
          ]} />
          {manual && (
            <div className="mt-4 border-t border-slate-100 pt-4">
              {hasProof ? (
                <button type="button" disabled={!r.has_proof_file} onClick={() => setShowProof(true)}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60">
                  <FileSearch className="size-4" aria-hidden />
                  {r.has_proof_file ? 'Ver el comprobante' : 'El cliente no adjuntó archivo'}
                </button>
              ) : (
                <p className="text-sm text-amber-700">El cliente todavía no envió ningún comprobante.</p>
              )}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Historial">
        <Timeline label="Historial de estados de la remesa" items={toTimeline(r.status_log)} />
      </Panel>

      <Modal open={showProof} onClose={() => setShowProof(false)} title="Comprobante de pago" widthClass="max-w-3xl">
        {showProof && <ProofViewer trackingId={r.tracking_id} />}
      </Modal>
    </div>
  )
}
