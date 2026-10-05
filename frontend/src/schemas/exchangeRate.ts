import { z } from 'zod'
import { toScaled } from '../lib/decimal'

function decimalField(maxDecimals: number, required: string) {
  return z
    .string()
    .trim()
    .min(1, required)
    .refine((value) => value === '' || toScaled(value, maxDecimals) !== null, {
      message: `Escribe un número válido (máximo ${maxDecimals} decimales).`,
    })
}

/** UX validation only: the backend applies the same rules and is the authority. */
export const exchangeRateSchema = z
  .object({
    currency: z.enum(['USD', 'EUR']),
    base_rate: decimalField(6, 'Ingresa la tasa base.').refine(
      (value) => {
        const scaled = toScaled(value, 6)
        return scaled === null || scaled > 0n
      },
      { message: 'La tasa base debe ser mayor que 0.' },
    ),
    standard_spread_percent: decimalField(2, 'Ingresa el margen estándar.').refine(
      (value) => {
        const scaled = toScaled(value, 2)
        return scaled === null || scaled < 10000n
      },
      { message: 'El margen debe ser menor que 100 por ciento.' },
    ),
    vip_spread_percent: decimalField(2, 'Ingresa el margen VIP.').refine(
      (value) => {
        const scaled = toScaled(value, 2)
        return scaled === null || scaled < 10000n
      },
      { message: 'El margen debe ser menor que 100 por ciento.' },
    ),
    is_active: z.boolean(),
  })
  .refine(
    (data) => {
      const standard = toScaled(data.standard_spread_percent, 2)
      const vip = toScaled(data.vip_spread_percent, 2)
      return standard === null || vip === null || vip <= standard
    },
    { path: ['vip_spread_percent'], message: 'El margen VIP no puede ser mayor que el estándar.' },
  )

export type ExchangeRateForm = z.infer<typeof exchangeRateSchema>
