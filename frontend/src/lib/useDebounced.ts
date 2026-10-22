import { useEffect, useState } from 'react'

/** The value once it has stopped changing for `delayMs` (what-if live mode: 150 ms, roadmap R2-P7). */
export function useDebounced<T>(value: T, delayMs: number): T {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return settled
}
