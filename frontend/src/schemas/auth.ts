import { z } from 'zod'

/**
 * Password rules from HU-AUTH-01. They are validated here only for UX; the
 * backend is the authority and applies the same rules (plus "too common" and
 * "too similar to the email").
 */
export const PASSWORD_RULES = [
  { id: 'length', label: 'Al menos 8 caracteres', error: 'La contraseña debe tener al menos 8 caracteres.', test: (value: string) => value.length >= 8 },
  { id: 'letter', label: 'Al menos una letra', error: 'La contraseña debe contener al menos una letra.', test: (value: string) => /\p{L}/u.test(value) },
  { id: 'digit', label: 'Al menos un número', error: 'La contraseña debe contener al menos un número.', test: (value: string) => /\p{Nd}/u.test(value) },
] as const

const emailSchema = z.string().trim().min(1, 'Ingresa tu correo electrónico.').email('Escribe un correo válido.')

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, 'Ingresa tu contraseña.'),
})
export type LoginForm = z.infer<typeof loginSchema>

export const registerSchema = z.object({
  email: emailSchema,
  password: z
    .string()
    .min(1, 'Crea una contraseña.')
    .superRefine((value, ctx) => {
      if (value.length === 0) return // already reported by min(1)
      for (const rule of PASSWORD_RULES) {
        if (!rule.test(value)) ctx.addIssue({ code: 'custom', message: rule.error })
      }
    }),
  first_name: z.string().trim().max(150, 'Máximo 150 caracteres.'),
  last_name: z.string().trim().max(150, 'Máximo 150 caracteres.'),
})
export type RegisterForm = z.infer<typeof registerSchema>
