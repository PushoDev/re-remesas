import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { quoteRemittance } from '../services/remittanceService'
import type { CurrencyCode } from '../types/remittances'
import { useAuth } from './useAuth'

const REFRESH_MS = 30_000

/** The server's quote for an amount. Refreshes while open so a rate change shows up by itself. */
export function useRemittanceQuote(amount: string, currency: CurrencyCode, enabled: boolean) {
  const { user } = useAuth()
  // A change of membership changes the rate, so it is part of the cache key.
  const audience = user ? user.profile.membership_status : 'anonymous'

  return useQuery({
    queryKey: ['remittance-quote', amount, currency, audience],
    queryFn: () => quoteRemittance({ amount, currency }),
    enabled,
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
  })
}
