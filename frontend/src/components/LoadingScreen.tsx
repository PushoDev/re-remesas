import { Loader2 } from 'lucide-react'

export default function LoadingScreen() {
  return (
    <div role="status" className="flex min-h-dvh items-center justify-center bg-slate-50">
      <Loader2 className="size-8 animate-spin text-blue-700" aria-hidden />
      <span className="sr-only">Cargando…</span>
    </div>
  )
}
