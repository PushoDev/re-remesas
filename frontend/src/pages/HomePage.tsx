import { useEffect, useState } from 'react'
import { apiClient } from '../services/apiClient'

type HealthStatus = 'checking' | 'ok' | 'error'

export default function HomePage() {
  const [status, setStatus] = useState<HealthStatus>('checking')

  useEffect(() => {
    apiClient
      .get('/health/')
      .then(() => setStatus('ok'))
      .catch(() => setStatus('error'))
  }, [])

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50">
      <h1 className="text-3xl font-semibold text-slate-900">Re & Re</h1>
      <p className="text-slate-600">Remesas & Recargas</p>
      <p className="rounded-full px-4 py-1 text-sm font-medium data-[status=ok]:bg-emerald-100 data-[status=ok]:text-emerald-700 data-[status=error]:bg-red-100 data-[status=error]:text-red-700 data-[status=checking]:bg-slate-200 data-[status=checking]:text-slate-700" data-status={status}>
        Backend: {status}
      </p>
    </main>
  )
}
