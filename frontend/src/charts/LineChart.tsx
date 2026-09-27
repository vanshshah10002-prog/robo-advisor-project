import { scaleLinear, scaleUtc, type ScaleLinear, type ScaleTime } from 'd3-scale'
import { area, line } from 'd3-shape'
import { useMemo, type ReactNode } from 'react'
import { EMPTY, date } from '@/lib/format'
import type { ProvenanceKind } from '@/ui/provenance'
import { Crosshair, EndLabels, HitArea, XAxis, YGrid, type EndLabel } from './Axes'
import { ChartFrame } from './ChartFrame'
import { DataTable, type Column } from './DataTable'
import { useCursor, useElementWidth } from './hooks'
import { Legend, type LegendItem } from './Legend'
import { describeRows } from './model'
import {
    extent,
    nearestIndex,
    paddedDomain,
    parseDay,
    plotBox,
    sampleIndices,
    spreadLabels,
    tickCount,
    timeTickFormat,
} from './scales'
import { Announce, ChartTooltip, type TooltipRow } from './Tooltip'
import styles from './Chart.module.css'

export interface LineSeries {
    key: string
    label: string
    colour: string
    values: readonly (number | null)[]
    /** line: 2px. area: 2px over a 10% fill down to zero. reference: dashed, for what went in. */
    variant?: 'line' | 'area' | 'reference'
}

export interface LineChartProps {
    /** "YYYY-MM-DD", one per value, ascending. */
    dates: readonly string[]
    series: readonly LineSeries[]
    /** Formats values in the tooltip, table and end labels. */
    format: (v: number) => string
    /** Formats the value axis; defaults to `format`. */
    axisFormat?: (v: number) => string
    /** A labelled rule across the plot, such as the amount first invested. */
    baseline?: { value: number; label: string }
    title: string
    summary?: string
    provenance?: ProvenanceKind
    notes?: ReactNode
    pending?: boolean
    /** Shown instead of the chart when there are fewer than two dates. */
    empty?: string
    height?: number
    /** The table twin samples long series down to about this many rows. */
    tableRows?: number
}

type Show = (v: number | null | undefined) => string
type Linear = ScaleLinear<number, number>
type Time = ScaleTime<number, number>

const DEFAULT_HEIGHT = 300
const AREA_OPACITY = 0.1
const TABLE_ROWS = 40
const X_TICK_SPACING = 96
const Y_TICK_SPACING = 56

const isValue = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v)

function lastValue(values: readonly (number | null)[]): number | null {
    for (let i = values.length - 1; i >= 0; i -= 1) {
        const v = values[i]
        if (isValue(v)) return v
    }
    return null
}

/** Values over time: every series on one axis, and the crosshair reads them all. */
export function LineChart(props: LineChartProps) {
    const { dates, series, format, title, summary, provenance, notes, pending, empty, tableRows = TABLE_ROWS } = props
    const show: Show = (v) => (isValue(v) ? format(v) : EMPTY)
    const columns: Column<number>[] = [
        { key: 'date', label: 'Date', render: (i) => date(dates[i]) },
        ...series.map((s) => ({ key: s.key, label: s.label, numeric: true, render: (i: number) => show(s.values[i]) })),
    ]
    const legend: LegendItem[] = series.map((s) => ({
        key: s.key,
        label: s.label,
        colour: s.colour,
        mark: s.variant === 'reference' ? 'dash' : 'line',
    }))

    return (
        <ChartFrame
            title={title}
            summary={summary}
            provenance={provenance}
            notes={notes}
            pending={pending}
            empty={dates.length < 2 ? (empty ?? 'Not enough history to draw yet.') : undefined}
            legend={series.length > 1 ? <Legend items={legend} /> : undefined}
            table={<DataTable caption={title} columns={columns} rows={sampleIndices(dates.length, tableRows)} rowKey={(i) => i} />}
        >
            <LinePlot {...props} show={show} />
        </ChartFrame>
    )
}

function LinePlot({ dates, series, format, axisFormat = format, baseline, title, height = DEFAULT_HEIGHT, show }: LineChartProps & { show: Show }) {
    const [ref, width] = useElementWidth<HTMLDivElement>()
    const cursor = useCursor(dates.length)
    const times = useMemo(() => dates.map((d) => parseDay(d).getTime()), [dates])
    const box = plotBox(width, height)
    const x = scaleUtc().domain([times[0], times[times.length - 1]]).range([0, box.innerW])
    const zero = series.some((s) => s.variant === 'area')
    const y = scaleLinear()
        .domain(paddedDomain(extent([...series.map((s) => s.values), baseline ? [baseline.value] : []]), { zero }))
        .range([box.innerH, 0])
        .nice()
    const dateTicks = x.ticks(tickCount(box.innerW, X_TICK_SPACING))
    const tickLabel = timeTickFormat(dateTicks)
    const i = cursor.index
    const rows = i === null ? [] : lineRows(series, i, show)
    const dots = (at: number) =>
        series.flatMap((s) => (isValue(s.values[at]) ? [{ key: s.key, cy: y(s.values[at] as number), fill: s.colour }] : []))

    return (
        <div className={styles.plot} ref={ref} role="img" aria-label={lineLabel(title, dates, series, show)} {...cursor.keyboard}>
            <svg width={width} height={height} aria-hidden="true" focusable="false">
                <g transform={`translate(${box.margin.left},${box.margin.top})`}>
                    <YGrid ticks={y.ticks(tickCount(box.innerH, Y_TICK_SPACING))} y={y} width={box.innerW} format={axisFormat} />
                    <LineMarks series={series} times={times} x={x} y={y} baseline={baseline} width={box.innerW} />
                    <XAxis ticks={dateTicks.map((d) => ({ key: d.getTime(), at: x(d), label: tickLabel(d) }))} top={box.innerH} width={box.innerW} />
                    {box.withEnds && <EndLabels labels={lineEnds(series, y, format)} x={box.innerW + 8} spread={(ys) => spreadLabels(ys, 14)} />}
                    {i !== null && <Crosshair x={x(times[i])} height={box.innerH} dots={dots(i)} />}
                    <HitArea
                        width={box.innerW}
                        height={box.innerH}
                        onMove={(px) => cursor.point(nearestIndex(times, x.invert(px).getTime()))}
                        onLeave={() => cursor.point(null)}
                    />
                </g>
            </svg>
            {i !== null && <ChartTooltip title={date(dates[i])} rows={rows} x={box.margin.left + x(times[i])} y={box.margin.top} width={width} />}
            <Announce text={i !== null && cursor.fromKeyboard ? describeRows(date(dates[i]), rows) : ''} />
        </div>
    )
}

interface LineMarksProps {
    series: readonly LineSeries[]
    times: readonly number[]
    x: Time
    y: Linear
    baseline?: { value: number; label: string }
    width: number
}

function LineMarks({ series, times, x, y, baseline, width }: LineMarksProps) {
    const linePath = (vs: readonly (number | null)[]) =>
        line<number | null>()
            .defined(isValue)
            .x((_, i) => x(times[i]))
            .y((v) => y(v ?? 0))(vs as (number | null)[]) ?? ''
    const areaPath = (vs: readonly (number | null)[]) =>
        area<number | null>()
            .defined(isValue)
            .x((_, i) => x(times[i]))
            .y0(y(0))
            .y1((v) => y(v ?? 0))(vs as (number | null)[]) ?? ''

    return (
        <>
            {baseline && (
                <g>
                    <line className={styles.baseline} x1={0} x2={width} y1={y(baseline.value)} y2={y(baseline.value)} />
                    <text className={styles.annotation} x={width - 4} y={y(baseline.value) - 6} textAnchor="end">
                        {baseline.label}
                    </text>
                </g>
            )}
            {series.map((s) =>
                s.variant === 'area' ? <path key={`${s.key}-fill`} d={areaPath(s.values)} style={{ fill: s.colour }} fillOpacity={AREA_OPACITY} /> : null,
            )}
            {series.map((s) => (
                <path
                    key={s.key}
                    d={linePath(s.values)}
                    fill="none"
                    style={{ stroke: s.colour }}
                    strokeWidth={2}
                    strokeLinejoin="round"
                    strokeDasharray={s.variant === 'reference' ? '4 3' : undefined}
                />
            ))}
        </>
    )
}

function lineRows(series: readonly LineSeries[], i: number, show: Show): TooltipRow[] {
    return series.map((s) => ({
        key: s.key,
        label: s.label,
        value: show(s.values[i]),
        colour: s.colour,
        mark: s.variant === 'reference' ? 'dash' : 'line',
    }))
}

function lineEnds(series: readonly LineSeries[], y: Linear, format: (v: number) => string): EndLabel[] {
    return series.flatMap((s) => {
        const end = lastValue(s.values)
        return end === null ? [] : [{ key: s.key, y: y(end), text: format(end), strong: s.variant !== 'reference' }]
    })
}

function lineLabel(title: string, dates: readonly string[], series: readonly LineSeries[], show: Show): string {
    const span = `${title}, ${date(dates[0])} to ${date(dates[dates.length - 1])}.`
    const ends = series.map((s) => `${s.label} ends at ${show(lastValue(s.values))}`).join('; ')
    return `${span} ${ends ? `${ends}. ` : ''}Use the arrow keys to read each date, or switch to the table.`
}
