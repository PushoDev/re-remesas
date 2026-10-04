import { describe, expect, it } from 'vitest'
import { recipientSchema } from './remittance'

const cash = {
  recipient_name: 'Rosa Pérez', recipient_phone: '5123 4567', delivery_method: 'CASH_DELIVERY',
  recipient_address: 'Calle 23 #456', recipient_account: '',
}
const transfer = { ...cash, delivery_method: 'LOCAL_TRANSFER', recipient_address: '', recipient_account: '9225 1234 5678 9012' }

function problems(data: Record<string, unknown>): Record<string, string> {
  const result = recipientSchema.safeParse(data)
  if (result.success) return {}
  return Object.fromEntries(result.error.issues.map((issue) => [String(issue.path[0]), issue.message]))
}

describe('recipientSchema', () => {
  it('accepts a cash delivery and a local transfer', () => {
    expect(recipientSchema.safeParse(cash).success).toBe(true)
    expect(recipientSchema.safeParse(transfer).success).toBe(true)
  })

  it('cash delivery needs an address', () => {
    expect(problems({ ...cash, recipient_address: '  ' }).recipient_address).toMatch(/dirección/)
  })

  it('a local transfer needs an account, not an address', () => {
    expect(problems({ ...transfer, recipient_account: '' }).recipient_account).toMatch(/cuenta o tarjeta/)
    expect(recipientSchema.safeParse({ ...transfer, recipient_address: '' }).success).toBe(true)
  })

  it.each(['123', '9225-1234-ABCD-9012', '1'.repeat(21)])('rejects the account %j', (account) => {
    expect(problems({ ...transfer, recipient_account: account }).recipient_account).toMatch(/12 y 20 dígitos/)
  })

  it('accepts spaces and dashes in the account', () => {
    expect(recipientSchema.safeParse({ ...transfer, recipient_account: '9225-1234-5678-9012' }).success).toBe(true)
  })

  it.each(['', '   ', 'A'])('rejects the name %j', (name) => {
    expect(problems({ ...cash, recipient_name: name }).recipient_name).toBeTruthy()
  })

  it.each(['', '123', '41234567', '+54 51234567'])('rejects the phone %j', (phone) => {
    expect(problems({ ...cash, recipient_phone: phone }).recipient_phone).toBeTruthy()
  })

  it('rejects an unknown delivery method', () => {
    expect(recipientSchema.safeParse({ ...cash, delivery_method: 'DRONE' }).success).toBe(false)
  })
})
