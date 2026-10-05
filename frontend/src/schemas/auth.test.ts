import { describe, expect, it } from 'vitest'
import { loginSchema, registerSchema } from './auth'

const valid = { email: 'ana@example.com', password: 'Tr3sPatos88x', first_name: '', last_name: '' }

function passwordErrors(password: string): string[] {
  const result = registerSchema.safeParse({ ...valid, password })
  return result.success ? [] : result.error.issues.filter((i) => i.path[0] === 'password').map((i) => i.message)
}

describe('registerSchema', () => {
  it('accepts a valid registration (names are optional)', () => {
    expect(registerSchema.safeParse(valid).success).toBe(true)
  })

  it('trims the email', () => {
    const result = registerSchema.parse({ ...valid, email: '  ana@example.com ' })
    expect(result.email).toBe('ana@example.com')
  })

  it('rejects an invalid email', () => {
    expect(registerSchema.safeParse({ ...valid, email: 'no-es-correo' }).success).toBe(false)
  })

  it('rejects a short password', () => {
    expect(passwordErrors('Ab1xyz')).toContain('La contraseña debe tener al menos 8 caracteres.')
  })

  it('rejects a password without numbers', () => {
    expect(passwordErrors('SoloLetrasAqui')).toEqual(['La contraseña debe contener al menos un número.'])
  })

  it('rejects a password without letters', () => {
    expect(passwordErrors('48273650192')).toEqual(['La contraseña debe contener al menos una letra.'])
  })

  it('accepts accented letters, like the backend does', () => {
    expect(passwordErrors('Contraseña2026')).toEqual([])
  })

  it('asks for a password when empty', () => {
    expect(passwordErrors('')).toEqual(['Crea una contraseña.'])
  })
})

describe('loginSchema', () => {
  it('requires email and password', () => {
    const result = loginSchema.safeParse({ email: '', password: '' })
    expect(result.success).toBe(false)
  })

  it('does not apply the registration password rules to the login', () => {
    expect(loginSchema.safeParse({ email: 'ana@example.com', password: 'x' }).success).toBe(true)
  })
})
