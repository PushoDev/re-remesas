import { Check } from 'lucide-react'

export default function StepIndicator({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol aria-label="Pasos del envío" className="flex items-center gap-2 text-sm">
      {steps.map((label, index) => {
        const number = index + 1
        const done = number < current
        const active = number === current
        return (
          <li key={label} aria-current={active ? 'step' : undefined} className="flex items-center gap-2">
            <span
              className={`flex size-7 items-center justify-center rounded-full text-xs font-semibold ${
                done ? 'bg-emerald-600 text-white' : active ? 'bg-blue-700 text-white' : 'bg-slate-200 text-slate-600'
              }`}
            >
              {done ? <Check className="size-4" aria-hidden /> : number}
            </span>
            <span className={`hidden sm:inline ${active ? 'font-semibold text-slate-900' : 'text-slate-500'}`}>{label}</span>
            {number < steps.length && <span className="h-px w-4 bg-slate-300 sm:w-8" aria-hidden />}
          </li>
        )
      })}
    </ol>
  )
}
