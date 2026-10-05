import { useEffect, useState } from 'react'

/** The value, but only after it stops changing for `delay` ms (so a quote is not asked on every keystroke). */
export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debounced
}
