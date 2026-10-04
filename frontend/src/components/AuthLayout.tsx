import type { ReactNode } from 'react'
import loginBackground from '../assets/login-bg.webp'

interface AuthLayoutProps {
  title: string
  subtitle: string
  children: ReactNode
  /** Link to the sibling screen (login <-> register). */
  footer: ReactNode
  /** Optional extra block under the card (development helpers). */
  aside?: ReactNode
}

export default function AuthLayout({ title, subtitle, children, footer, aside }: AuthLayoutProps) {
  return (
    <main className="relative isolate flex min-h-dvh items-center justify-center px-4 py-10">
      <img src={loginBackground} alt="" className="absolute inset-0 -z-20 h-full w-full object-cover" />
      <div className="absolute inset-0 -z-10 bg-slate-950/40" aria-hidden />

      <div className="w-full max-w-md">
        <section className="rounded-2xl bg-white/95 p-8 shadow-2xl backdrop-blur">
          <header className="mb-6 text-center">
            <p className="text-2xl font-bold tracking-tight text-blue-800">Re &amp; Re</p>
            <p className="text-sm text-slate-500">Remesas &amp; Recargas</p>
            <h1 className="mt-5 text-xl font-semibold text-slate-900">{title}</h1>
            <p className="mt-1 text-sm text-slate-600">{subtitle}</p>
          </header>

          {children}

          <p className="mt-6 text-center text-sm text-slate-600">{footer}</p>
        </section>
        {aside}
      </div>
    </main>
  )
}
