import { clsx } from 'clsx'
import { anchorOf, spacedLabels, type AxisLabel } from './scales'
import styles from './Chart.module.css'

const LABEL_GAP = 8

/** Horizontal hairlines with their values on the left. Zero, if shown, is drawn as the baseline. */
export function YGrid({
    ticks,
    y,
    width,
    format,
}: {
    ticks: readonly number[]
    y: (v: number) => number
    width: number
    format: (v: number) => string
}) {
    return (
        <>
            <g className={styles.grid} aria-hidden="true">
                {ticks.map((t) => (
                    <line key={t} x1={0} x2={width} y1={y(t)} y2={y(t)} className={clsx(t === 0 && styles.baseline)} />
                ))}
            </g>
            <g className={styles.axis} aria-hidden="true">
                {ticks.map((t) => (
                    <text key={t} x={-LABEL_GAP} y={y(t)} dy="0.32em" textAnchor="end">
                        {format(t)}
                    </text>
                ))}
            </g>
        </>
    )
}

export type XTick = AxisLabel

/** Labels under the plot. Labels near an edge anchor to it rather than overhang, and none overlap. */
export function XAxis({ ticks, top, width }: { ticks: readonly XTick[]; top: number; width: number }) {
    return (
        <g className={styles.axis} aria-hidden="true">
            {spacedLabels(ticks, width).map((t) => (
                <text key={t.key} x={t.at} y={top + 18} textAnchor={anchorOf(t.at, width)}>
                    {t.label}
                </text>
            ))}
        </g>
    )
}

export interface EndLabel {
    key: string
    y: number
    text: string
    strong?: boolean
}

/** Values written at the right-hand end of their lines, nudged apart so none collide. */
export function EndLabels({ labels, x, spread }: { labels: readonly EndLabel[]; x: number; spread: (ys: number[]) => number[] }) {
    const sorted = [...labels].sort((a, b) => a.y - b.y)
    const ys = spread(sorted.map((l) => l.y))
    return (
        <g aria-hidden="true">
            {sorted.map((l, i) => (
                <text
                    key={l.key}
                    x={x}
                    y={ys[i]}
                    dy="0.32em"
                    className={clsx(styles.endLabel, l.strong && styles.endLabelStrong)}
                >
                    {l.text}
                </text>
            ))}
        </g>
    )
}

export interface CrosshairDot {
    key: string
    cy: number
    fill: string
}

/** The vertical rule at the cursor, with a dot where it meets each series. */
export function Crosshair({ x, height, dots }: { x: number; height: number; dots: readonly CrosshairDot[] }) {
    return (
        <g aria-hidden="true">
            <line className={styles.crosshair} x1={x} x2={x} y1={0} y2={height} />
            {dots.map((d) => (
                <circle key={d.key} className={styles.dot} cx={x} cy={d.cy} r={3.5} fill={d.fill} />
            ))}
        </g>
    )
}

/** A transparent layer over the plot that reports the pointer's x, in plot pixels. */
export function HitArea({
    width,
    height,
    onMove,
    onLeave,
}: {
    width: number
    height: number
    onMove: (px: number) => void
    onLeave: () => void
}) {
    return (
        <rect
            className={styles.hit}
            width={width}
            height={height}
            onPointerMove={(e) => onMove(e.clientX - e.currentTarget.getBoundingClientRect().left)}
            onPointerLeave={onLeave}
        />
    )
}
