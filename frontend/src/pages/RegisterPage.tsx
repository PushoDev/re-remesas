import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { Check, Circle, Loader2, UserPlus } from 'lucide-react'
import { useForm, useWatch } from 'react-hook-form'
import { Link, Navigate } from 'react-router-dom'
import { toast } from 'sonner'
import AuthLayout from '../components/AuthLayout'
import ErrorAlert from '../components/ErrorAlert'
import LoadingScreen from '../components/LoadingScreen'
import PasswordInput from '../components/PasswordInput'
import { useAuth } from '../hooks/useAuth'
import { parseApiError } from '../lib/apiErrors'
import { inputClass, primaryButtonClass } from '../lib/formStyles'
import { PASSWORD_RULES, registerSchema, type RegisterForm } from '../schemas/auth'
import type { RegisterRequest } from '../types/auth'

const FORM_FIELDS = ['email', 'password', 'first_name', 'last_name'] as const

export default function RegisterPage() {
  const { status, register: registerAccount } = useAuth()

  const {
    register,
    handleSubmit,
    setError,
    control,
    formState: { errors },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: '', password: '', first_name: '', last_name: '' },
  })

  const mutation = useMutation({
    mutationFn: registerAccount,
    onSuccess: () => toast.success('Cuenta creada. ¡Bienvenido a Re & Re!'),
    onError: (error) => {
      // Show backend validation messages under the field they belong to.
      const { fieldErrors } = parseApiError(error)
      for (const field of FORM_FIELDS) {
        if (fieldErrors[field]) setError(field, { message: fieldErrors[field].join(' ') })
      }
    },
  })

  const password = useWatch({ control, name: 'password' })

  if (status === 'loading') return <LoadingScreen />
  if (status === 'authenticated') return <Navigate to="/" replace />

  // Field errors are already under their inputs; only show the banner for the rest.
  const apiError = mutation.error ? parseApiError(mutation.error) : null
  const bannerMessage =
    apiError && !FORM_FIELDS.some((field) => apiError.fieldErrors[field]) ? apiError.message : null

  const onSubmit = (values: RegisterForm) => {
    const payload: RegisterRequest = { email: values.email, password: values.password }
    if (values.first_name) payload.first_name = values.first_name
    if (values.last_name) payload.last_name = values.last_name
    mutation.mutate(payload)
  }

  return (
    <AuthLayout
      title="Crea tu cuenta"
      subtitle="Envía remesas y recargas a tus seres queridos en Cuba."
      footer={
        <>
          ¿Ya tienes cuenta?{' '}
          <Link to="/login" className="font-semibold text-blue-700 hover:underline">
            Inicia sesión
          </Link>
        </>
      }
    >
      {bannerMessage && <ErrorAlert message={bannerMessage} />}

      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="first_name" className="text-sm font-medium text-slate-700">
              Nombre <span className="font-normal text-slate-400">(opcional)</span>
            </label>
            <input
              id="first_name"
              autoComplete="given-name"
              aria-invalid={errors.first_name ? 'true' : 'false'}
              className={inputClass}
              {...register('first_name')}
            />
            {errors.first_name && <p className="mt-1 text-sm text-red-600">{errors.first_name.message}</p>}
          </div>
          <div>
            <label htmlFor="last_name" className="text-sm font-medium text-slate-700">
              Apellido <span className="font-normal text-slate-400">(opcional)</span>
            </label>
            <input
              id="last_name"
              autoComplete="family-name"
              aria-invalid={errors.last_name ? 'true' : 'false'}
              className={inputClass}
              {...register('last_name')}
            />
            {errors.last_name && <p className="mt-1 text-sm text-red-600">{errors.last_name.message}</p>}
          </div>
        </div>

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
            autoComplete="new-password"
            aria-invalid={errors.password ? 'true' : 'false'}
            aria-describedby="password-rules password-error"
            {...register('password')}
          />
          {errors.password && (
            <p id="password-error" className="mt-1 text-sm text-red-600">
              {errors.password.message}
            </p>
          )}
          <ul id="password-rules" className="mt-2 space-y-1 text-sm" aria-label="Requisitos de la contraseña">
            {PASSWORD_RULES.map((rule) => {
              const met = rule.test(password)
              return (
                <li key={rule.id} className={`flex items-center gap-2 ${met ? 'text-emerald-700' : 'text-slate-500'}`}>
                  {met ? <Check className="size-4" aria-hidden /> : <Circle className="size-4" aria-hidden />}
                  {rule.label}
                  <span className="sr-only">{met ? ' (cumplido)' : ' (pendiente)'}</span>
                </li>
              )
            })}
          </ul>
        </div>

        <button type="submit" disabled={mutation.isPending} className={primaryButtonClass}>
          {mutation.isPending ? (
            <>
              <Loader2 className="size-5 animate-spin" aria-hidden />
              Creando cuenta…
            </>
          ) : (
            <>
              <UserPlus className="size-5" aria-hidden />
              Crear cuenta
            </>
          )}
        </button>
      </form>
    </AuthLayout>
  )
}
