import { useCountUp } from '@/lib/useCountUp'

/**
 * A headline figure that settles into place when the page opens. While it
 * counts, the moving digits are hidden from assistive technology, which
 * reads the figure itself, once.
 */
export function CountUp({ value, format }: { value: number; format: (n: number) => string }) {
    const shown = useCountUp(value)
    if (shown === null) return <>{format(value)}</>
    return (
        <>
            <span aria-hidden="true">{format(shown)}</span>
            <span className="visually-hidden">{format(value)}</span>
        </>
    )
}
