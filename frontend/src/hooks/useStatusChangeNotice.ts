import { useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { statusChangeMessage } from '../lib/remittanceTimeline'

/** While the page is open, flashes a notice when the status changes (an administrator acted, a payment landed). */
export function useStatusChangeNotice(status: string | undefined, label: string | undefined): void {
  const previous = useRef<string | undefined>(undefined)

  useEffect(() => {
    const message = statusChangeMessage(previous.current, status, label)
    if (message) toast.info(message, { duration: 8000 })
    previous.current = status
  }, [status, label])
}
