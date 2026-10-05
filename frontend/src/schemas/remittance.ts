import { z } from 'zod'
import { normalizeCubanMobile } from '../lib/phone'

/** Step 2 of the wizard. UX validation only: the backend applies the same rules. */
export const recipientSchema = z
  .object({
    recipient_name: z
      .string()
      .trim()
      .min(2, 'Ingresa el nombre completo del destinatario.')
      .max(120, 'El nombre es demasiado largo (máximo 120 caracteres).'),
    recipient_phone: z
      .string()
      .trim()
      .min(1, 'Ingresa el teléfono del destinatario.')
      .refine((value) => value === '' || normalizeCubanMobile(value) !== null, {
        message: 'Escribe un móvil cubano válido: +53 seguido de 8 dígitos que empiezan por 5.',
      }),
    delivery_method: z.enum(['CASH_DELIVERY', 'LOCAL_TRANSFER']),
    recipient_address: z.string().trim().max(255, 'La dirección es demasiado larga.'),
    recipient_account: z.string().trim().max(60, 'La cuenta es demasiado larga.'),
  })
  .superRefine((data, ctx) => {
    if (data.delivery_method === 'CASH_DELIVERY') {
      if (!data.recipient_address) {
        ctx.addIssue({ code: 'custom', path: ['recipient_address'], message: 'Ingresa la dirección donde se entregará el efectivo.' })
      }
      return
    }
    const account = data.recipient_account.replace(/[\s-]/g, '')
    if (!account) {
      ctx.addIssue({ code: 'custom', path: ['recipient_account'], message: 'Ingresa la cuenta o tarjeta que recibirá la transferencia.' })
    } else if (!/^\d{12,20}$/.test(account)) {
      ctx.addIssue({ code: 'custom', path: ['recipient_account'], message: 'La cuenta debe tener entre 12 y 20 dígitos.' })
    }
  })

export type RecipientForm = z.infer<typeof recipientSchema>
