import { Banknote, CreditCard } from 'lucide-react'
import type { ReactNode } from 'react'
import { PAYMENT_METHODS } from '../lib/paymentMethods'
import type { PaymentMethodCode } from '../types/memberships'

interface GroupProps {
  title: string
  icon: ReactNode
  note: string
  kind: 'online' | 'manual'
  value: PaymentMethodCode
  onChange: (code: PaymentMethodCode) => void
}

function MethodGroup({ title, icon, note, kind, value, onChange }: GroupProps) {
  return (
    <fieldset className="rounded-xl border border-slate-200 p-4">
      <legend className="flex items-center gap-2 px-1 text-sm font-semibold text-slate-800">
        {icon}
        {title}
      </legend>
      <p className="mb-2 text-xs text-slate-500">{note}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {PAYMENT_METHODS.filter((method) => method.kind === kind).map((method) => (
          <label
            key={method.code}
            className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm has-[:checked]:border-blue-600 has-[:checked]:bg-blue-50 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-blue-600"
          >
            <input
              type="radio"
              name="payment_method"
              value={method.code}
              checked={value === method.code}
              onChange={() => onChange(method.code)}
              className="size-4 accent-blue-700"
            />
            {method.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

interface PickerProps {
  value: PaymentMethodCode
  onChange: (code: PaymentMethodCode) => void
  /** Which groups to offer. Recharges only take online gateways: there is no way to attach a proof to them. */
  kinds?: ('online' | 'manual')[]
}

/** The seven payment methods in two groups: simulated online gateway, and manual (an administrator confirms). */
export default function PaymentMethodPicker({ value, onChange, kinds = ['online', 'manual'] }: PickerProps) {
  return (
    <div className="space-y-4">
      {kinds.includes('online') && <MethodGroup
        title="Pago en línea"
        icon={<CreditCard className="size-4" aria-hidden />}
        note="Se procesa en una pasarela de pruebas: en esta versión de demostración no se cobra nada."
        kind="online"
        value={value}
        onChange={onChange}
      />}
      {kinds.includes('manual') && <MethodGroup
        title="Pago manual"
        icon={<Banknote className="size-4" aria-hidden />}
        note="Pagas por fuera y un administrador verifica tu comprobante."
        kind="manual"
        value={value}
        onChange={onChange}
      />}
    </div>
  )
}
