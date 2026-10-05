import type { ReactNode } from 'react'

export interface TimelineItem {
  key: string | number
  title: string
  at: string
  /** Who/what moved it (administrator view only). */
  meta?: string
  note?: string
  /** A state change (filled dot) or just an annotation (hollow dot). */
  event?: boolean
  tone?: 'default' | 'success' | 'danger' | 'warning'
  icon?: ReactNode
}

const DOT: Record<NonNullable<TimelineItem['tone']>, string> = {
  default: 'bg-blue-600',
  success: 'bg-emerald-600',
  danger: 'bg-red-600',
  warning: 'bg-amber-500',
}
const dateTime = new Intl.DateTimeFormat('es', { dateStyle: 'medium', timeStyle: 'short' })

/** A vertical history. Oldest first, as the API sends it. */
export default function Timeline({ items, label }: { items: TimelineItem[]; label: string }) {
  return (
    <ol aria-label={label} className="relative space-y-5 border-l border-slate-200 pl-6">
      {items.map((item) => (
        <li key={item.key} className="relative">
          <span
            aria-hidden
            className={`absolute -left-[1.9rem] top-1 size-3 rounded-full ring-4 ring-white ${
              item.event === false ? 'border-2 border-slate-400 bg-white' : DOT[item.tone ?? 'default']
            }`}
          />
          <p className="text-sm font-semibold text-slate-900">{item.title}</p>
          <p className="text-xs text-slate-500">
            {dateTime.format(new Date(item.at))}
            {item.meta && <> · {item.meta}</>}
          </p>
          {item.note && <p className="mt-1 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">{item.note}</p>}
        </li>
      ))}
    </ol>
  )
}
