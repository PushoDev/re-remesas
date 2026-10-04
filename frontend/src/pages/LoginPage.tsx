import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { Loader2, LogIn } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { toast } from 'sonner'
import AuthLayout from '../components/AuthLayout'
import ErrorAlert from '../components/ErrorAlert'
import LoadingScreen from '../components/LoadingScreen'
import PasswordInput from '../components/PasswordInput'
import { useAuth } from '../hooks/useAuth'
import { parseApiError } from '../lib/apiErrors'
import { inputClass, primaryButtonClass } from '../lib/formStyles'
import { loginSchema, type LoginForm } from '../schemas/auth'

// Development-only shortcuts to log in with each seeded role (never in production builds).
const DEMO_ACCOUNTS = [
  { label: 'Administrador', email: 'admin@rere.test' },
  { label: 'Cliente gratuito', email: 'cliente@rere.test' },
  { label: 'Cliente VIP', email: 'vip@rere.test' },
  { label: 'VIP vencido', email: 'vip.vencido@rere.test' },
]
const DEMO_PASSWORD = 'Demo12345'

export default function LoginPage() {
  const { status, login } = useAuth()
  const location = useLocation()
  const wanted = (location.state as { from?: { pathname?: string; search?: string } } | null)?.from
  const from = wanted?.pathname ? `${wanted.pathname}${wanted.search ?? ''}` : '/'

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema), defaultValues: { email: '', password: '' } })

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (user) => {
      const plan = user.profile.membership_status === 'VIP' ? 'VIP' : 'Gratuita'
      toast.success(`Sesión iniciada · ${user.email} (${plan})`)
    },
  })

  if (status === 'loading') return <LoadingScreen />
  if (status === 'authenticated') return <Navigate to={from} replace />

  const apiError = mutation.error ? parseApiError(mutation.error) : null

  const demoAccounts = import.meta.env.DEV && (
    <aside className="mt-4 rounded-xl bg-slate-900/70 p-4 text-white backdrop-blur">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Cuentas de prueba · solo desarrollo</p>
      <div className="mt-2 grid grid-cols-2 gap-2">
        {DEMO_ACCOUNTS.map((account) => (
          <button
            key={account.email}
            type="button"
            onClick={() => {
              setValue('email', account.email, { shouldValidate: true })
              setValue('password', DEMO_PASSWORD, { shouldValidate: true })
            }}
            className="rounded-lg bg-white/10 px-3 py-2 text-left text-sm hover:bg-white/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-white"
          >
            <span className="block font-medium">{account.label}</span>
            <span className="block truncate text-xs text-slate-300">{account.email}</span>
          </button>
        ))}
      </div>
    </aside>
  )

  return (
    <AuthLayout
      title="Inicia sesión"
      subtitle="Accede para enviar remesas y recargas a Cuba."
      footer={
        <>
          ¿Aún no tienes cuenta?{' '}
          <Link to="/register" className="font-semibold text-blue-700 hover:underline">
            Crea una cuenta
          </Link>
        </>
      }
      aside={demoAccounts || undefined}
    >
      {apiError && <ErrorAlert message={apiError.message} />}

      <form onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate className="space-y-4">
        <div>
          <label htmlFor="email" className="text-sm font-medium text-slate-700">
            Correo electrónico
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="tu@correo.com"
            aria-invalid={errors.email ? 'true' : 'false'}
            aria-describedby={errors.email ? 'email-error' : undefined}
            className={inputClass}
            {...register('email')}
          />
          {errors.email && (
            <p id="email-error" className="mt-1 text-sm text-red-600">
              {errors.email.message}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="password" className="text-sm font-medium text-slate-700">
            Contraseña
          </label>
          <PasswordInput
            id="password"
            autoComplete="current-password"
            aria-invalid={errors.password ? 'true' : 'false'}
            aria-describedby={errors.password ? 'password-error' : undefined}
            {...register('password')}
          />
          {errors.password && (
            <p id="password-error" className="mt-1 text-sm text-red-600">
              {errors.password.message}
            </p>
          )}
        </div>

        <button type="submit" disabled={mutation.isPending} className={primaryButtonClass}>
          {mutation.isPending ? (
            <>
              <Loader2 className="size-5 animate-spin" aria-hidden />
              Entrando…
            </>
          ) : (
            <>
              <LogIn className="size-5" aria-hidden />
              Iniciar sesión
            </>
          )}
        </button>
      </form>
    </AuthLayout>
  )
}
