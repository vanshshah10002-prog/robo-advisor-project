import styles from './Chart.module.css'

export interface SparklineProps {
    values: readonly number[]
    /** What it shows, in words, for screen readers: "Value over 3 months, from £50,000 to £51,240". */
    label: string
    width?: number
    height?: number
}

const PAD = 2

/** A small trend line with no axes, for a table cell. Fewer than two values draws nothing. */
export function Sparkline({ values, label, width = 96, height = 28 }: SparklineProps) {
    if (values.length < 2) return null
    const lo = Math.min(...values)
    const span = Math.max(...values) - lo
    const x = (i: number) => PAD + (i / (values.length - 1)) * (width - 2 * PAD)
    // An unchanged series runs through the middle rather than along the floor.
    const y = (v: number) => (span === 0 ? height / 2 : height - PAD - ((v - lo) / span) * (height - 2 * PAD))
    const points = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
    const last = values.length - 1

    return (
        <svg className={styles.sparkline} width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
            <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
            <circle cx={x(last)} cy={y(values[last])} r="2" fill="currentColor" />
        </svg>
    )
}
