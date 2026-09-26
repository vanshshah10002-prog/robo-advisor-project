import { clsx } from 'clsx'
import { useId, type CSSProperties, type ReactNode } from 'react'
import styles from './Slider.module.css'

export interface SliderProps {
    id?: string
    label: ReactNode
    hint?: ReactNode
    /** The values it can take, ascending. The slider moves between them one stop at a time. */
    stops: readonly number[]
    value: number
    onChange: (value: number) => void
    /** The figure shown beside the label and under each stop: 6 → "6". */
    format: (value: number) => string
    /** What a screen reader says for a value: 6 → "Level 6 of 10, your level". */
    describe?: (value: number) => string
    className?: string
}

/** Index of the stop nearest to `value`, so a value between stops still shows sensibly. */
function nearestStop(stops: readonly number[], value: number): number {
    return stops.reduce((best, s, i) => (Math.abs(s - value) < Math.abs(stops[best] - value) ? i : best), 0)
}

/**
 * A native range input over a fixed set of stops: arrows, Home/End and Page
 * keys all work, and the value is spoken through `aria-valuetext`.
 */
export function Slider({ id, label, hint, stops, value, onChange, format, describe, className }: SliderProps) {
    const generated = useId()
    const inputId = id ?? generated
    const hintId = hint ? `${inputId}-hint` : undefined
    const index = nearestStop(stops, value)
    const last = Math.max(1, stops.length - 1)
    const fill = { '--fill': `${(index / last) * 100}%` } as CSSProperties

    return (
        <div className={clsx(styles.slider, className)}>
            <div className={styles.head}>
                <label className={styles.label} htmlFor={inputId}>
                    {label}
                </label>
                <output className={styles.value} htmlFor={inputId} aria-hidden="true">
                    {format(stops[index])}
                </output>
            </div>
            {hint && (
                <p id={hintId} className={styles.hint}>
                    {hint}
                </p>
            )}
            <input
                id={inputId}
                type="range"
                className={styles.range}
                style={fill}
                min={0}
                max={stops.length - 1}
                step={1}
                value={index}
                disabled={stops.length < 2}
                aria-describedby={hintId}
                aria-valuetext={(describe ?? format)(stops[index])}
                onChange={(e) => onChange(stops[Number(e.target.value)])}
            />
            <ol className={styles.stops} aria-hidden="true">
                {stops.map((s, i) => (
                    <li key={s} className={clsx(i === index && styles.current)} style={{ left: `${(i / last) * 100}%` }}>
                        {format(s)}
                    </li>
                ))}
            </ol>
        </div>
    )
}
