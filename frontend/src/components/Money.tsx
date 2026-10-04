import { formatMoney } from '../lib/money'

interface MoneyProps {
  amount: string
  currency: string
  className?: string
}

/** Every amount in the app goes through this: same separators, same currency placement. */
export default function Money({ amount, currency, className = '' }: MoneyProps) {
  return <span className={`tabular-nums ${className}`}>{formatMoney(amount, currency)}</span>
}
