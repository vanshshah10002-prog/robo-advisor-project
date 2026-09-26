import { useEffect, useState } from 'react'

/**
 * The value, once it has stopped changing for `delay` ms. Values are compared
 * by content, so a new object with the same fields does not restart the wait.
 */
export function useDebouncedValue<T>(value: T, delay: number): T {
    const [settled, setSettled] = useState(value)
    const key = JSON.stringify(value)

    useEffect(() => {
        const timer = window.setTimeout(() => setSettled(value), delay)
        return () => window.clearTimeout(timer)
        // `key` stands for `value`: content changes restart the wait, identity changes do not.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [key, delay])

    return settled
}
