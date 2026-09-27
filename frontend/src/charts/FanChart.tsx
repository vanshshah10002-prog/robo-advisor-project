import { scaleLinear, type ScaleLinear } from 'd3-scale'
import { area, curveMonotoneX, line } from 'd3-shape'
import type { ReactNode } from 'react'
import { money, moneyCompact } from '@/lib/format'
import { CHART_INK } from '@/lib/palette'
import { Term } from '@/ui/Term'
import { Crosshair, EndLabels, HitArea, XAxis, YGrid, type EndLabel } from './Axes'
import { ChartFrame } from './ChartFrame'
import { DataTable, type Column } from './DataTable'
import { useCursor, useElementWidth } from './hooks'
import { Legend, type LegendItem, type Mark } from './Legend'
import { describeRows } from './model'
import { extent, nearestIndex, paddedDomain, plotBox, spreadLabels, tickCount } from './scales'
import { Announce, ChartTooltip, type TooltipRow } from './Tooltip'
import styles from './Chart.module.css'

export interface FanData {
    years: readonly number[]
    p10: readonly number[]
    p25: readonly number[]
    p50: readonly number[]
    p75: readonly number[]
    p90: readonly number[]
    /** Money put in by each year: the lump sum plus contributions to date. */
    paidIn?: readonly number[]
}

export interface FanChartProps {
    data: FanData
    title: string
    summary?: string
    notes?: ReactNode
    pending?: boolean
    goal?: number | null
    /** Calendar year of `years[0]`. Without it the axis reads "Now", "5 yrs"… */
    startYear?: number
    height?: number
}

type Percentile = 'p90' | 'p75' | 'p50' | 'p25' | 'p10'
type Linear = ScaleLinear<number, number>

/**
 * Top to bottom, as they stack on the chart; each keyed to the band whose
 * edge it is. `reading` is the probability of ending beyond that edge, for
 * the readout; `column` is the percentile's name, for the table.
 */
const PERCENTILES: readonly { key: Percentile; reading: string; column: string; colour: string; mark: Mark }[] = [
    { key: 'p90', reading: '10% probability above', column: '90th percentile', colour: CHART_INK.bandOuter, mark: 'band' },
    { key: 'p75', reading: '25% probability above', column: '75th percentile', colour: CHART_INK.bandInner, mark: 'band' },
    { key: 'p50', reading: 'Median', column: 'Median', colour: CHART_INK.median, mark: 'line' },
    { key: 'p25', reading: '25% probability below', column: '25th percentile', colour: CHART_INK.bandInner, mark: 'band' },
    { key: 'p10', reading: '10% probability below', column: '10th percentile', colour: CHART_INK.bandOuter, mark: 'band' },
]

const DEFAULT_HEIGHT = 320
const PAID_IN = CHART_INK.axis
const X_TICK_SPACING = 88
const Y_TICK_SPACING = 56

interface YearNames {
    /** Short, for the axis: "2031" or "5 yrs". */
    label: (y: number) => string
    /** Full, for the readout and table: "2031, year 5" or "Year 5". */
    title: (y: number) => string
}

function yearNames(startYear?: number): YearNames {
    if (startYear !== undefined) {
        return {
            label: (y) => String(startYear + y),
            title: (y) => `${startYear + y}${y === 0 ? ', now' : `, year ${y}`}`,
        }
    }
    return {
        label: (y) => (y === 0 ? 'Now' : `${y} yr${y === 1 ? '' : 's'}`),
        title: (y) => (y === 0 ? 'Now' : `Year ${y}`),
    }
}

/**
 * The future as a range: the 80% and 50% probability ranges of the simulated
 * outcomes as nested bands, the median as the one line, and what was paid in
 * beneath.
 */
export function FanChart({ data, title, summary, notes, pending, goal, startYear, height = DEFAULT_HEIGHT }: FanChartProps) {
    const years = yearNames(startYear)
    return (
        <ChartFrame
            title={title}
            summary={summary}
            provenance="simulated"
            notes={notes}
            pending={pending}
            empty={data.years.length < 2 ? 'Not enough years to draw a projection.' : undefined}
            legend={<Legend items={fanLegend(Boolean(data.paidIn))} />}
            table={<FanTable data={data} title={title} yearTitle={years.title} />}
        >
            <FanPlot data={data} title={title} goal={goal} height={height} years={years} />
        </ChartFrame>
    )
}

interface FanPlotProps {
    data: FanData
    title: string
    goal?: number | null
    height: number
    years: YearNames
}

function FanPlot({ data, title, goal, height, years }: FanPlotProps) {
    const [ref, width] = useElementWidth<HTMLDivElement>()
    const cursor = useCursor(data.years.length)
    const box = plotBox(width, height)
    const x = scaleLinear().domain([data.years[0], data.years[data.years.length - 1]]).range([0, box.innerW])
    const y = scaleLinear()
        .domain(paddedDomain(extent([data.p10, data.p90, data.paidIn ?? [], goal ? [goal] : []]), { zero: true }))
        .range([box.innerH, 0])
        .nice()
    const xTicks = x
        .ticks(tickCount(box.innerW, X_TICK_SPACING))
        .filter(Number.isInteger)
        .map((t) => ({ key: t, at: x(t), label: years.label(t) }))
    const i = cursor.index
    const rows = i === null ? [] : fanRows(data, i)
    const dots = (at: number) => (['p90', 'p50', 'p10'] as const).map((k) => ({ key: k, cy: y(data[k][at]), fill: CHART_INK.median }))

    return (
        <div className={styles.plot} ref={ref} role="img" aria-label={fanLabel(title, data, years.label)} {...cursor.keyboard}>
            <svg width={width} height={height} aria-hidden="true" focusable="false">
                <g transform={`translate(${box.margin.left},${box.margin.top})`}>
                    <YGrid ticks={y.ticks(tickCount(box.innerH, Y_TICK_SPACING))} y={y} width={box.innerW} format={moneyCompact} />
                    <FanMarks data={data} x={x} y={y} goal={goal} width={box.innerW} />
                    <XAxis ticks={xTicks} top={box.innerH} width={box.innerW} />
                    {box.withEnds && <EndLabels labels={fanEnds(data, y)} x={box.innerW + 8} spread={(ys) => spreadLabels(ys, 14)} />}
                    {i !== null && <Crosshair x={x(data.years[i])} height={box.innerH} dots={dots(i)} />}
                    <HitArea
                        width={box.innerW}
                        height={box.innerH}
                        onMove={(px) => cursor.point(nearestIndex(data.years, x.invert(px)))}
                        onLeave={() => cursor.point(null)}
                    />
                </g>
            </svg>
            {i !== null && (
                <ChartTooltip title={years.title(data.years[i])} rows={rows} x={box.margin.left + x(data.years[i])} y={box.margin.top} width={width} />
            )}
            <Announce text={i !== null && cursor.fromKeyboard ? describeRows(years.title(data.years[i]), rows) : ''} />
        </div>
    )
}

function FanMarks({ data, x, y, goal, width }: { data: FanData; x: Linear; y: Linear; goal?: number | null; width: number }) {
    const band = (lo: readonly number[], hi: readonly number[]) =>
        area<number>()
            .x((_, i) => x(data.years[i]))
            .y0((_, i) => y(lo[i]))
            .y1((_, i) => y(hi[i]))
            .curve(curveMonotoneX)(data.years as number[]) ?? ''
    const path = (vs: readonly number[]) =>
        line<number>()
            .x((_, i) => x(data.years[i]))
            .y((v) => y(v))
            .curve(curveMonotoneX)(vs as number[]) ?? ''

    return (
        <>
            <path d={band(data.p10, data.p90)} style={{ fill: CHART_INK.bandOuter }} />
            <path d={band(data.p25, data.p75)} style={{ fill: CHART_INK.bandInner }} />
            {data.paidIn && <path d={path(data.paidIn)} fill="none" style={{ stroke: PAID_IN }} strokeWidth={2} strokeDasharray="4 3" />}
            <path d={path(data.p50)} fill="none" style={{ stroke: CHART_INK.median }} strokeWidth={2} strokeLinejoin="round" />
            {goal ? (
                <g>
                    <line x1={0} x2={width} y1={y(goal)} y2={y(goal)} className={styles.baseline} strokeDasharray="1 3" />
                    <text x={4} y={y(goal) - 6} className={styles.annotation}>
                        Goal {moneyCompact(goal)}
                    </text>
                </g>
            ) : null}
        </>
    )
}

function fanRows(data: FanData, i: number): TooltipRow[] {
    const rows: TooltipRow[] = PERCENTILES.map((p) => ({
        key: p.key,
        label: p.reading,
        value: money(data[p.key][i]),
        colour: p.colour,
        mark: p.mark,
    }))
    return data.paidIn ? [...rows, { key: 'paid', label: 'Paid in', value: money(data.paidIn[i]), colour: PAID_IN, mark: 'dash' }] : rows
}

function fanLegend(hasPaidIn: boolean): LegendItem[] {
    const items: LegendItem[] = [
        { key: 'p50', label: <Term explain="median">Median</Term>, colour: CHART_INK.median, mark: 'line' },
        { key: 'inner', label: <Term explain="range50">50% probability range</Term>, colour: CHART_INK.bandInner, mark: 'band' },
        { key: 'outer', label: <Term explain="range80">80% probability range</Term>, colour: CHART_INK.bandOuter, mark: 'band' },
    ]
    return hasPaidIn ? [...items, { key: 'paid', label: 'Paid in', colour: PAID_IN, mark: 'dash' }] : items
}

function fanEnds(data: FanData, y: Linear): EndLabel[] {
    const last = data.years.length - 1
    return [
        { key: 'p90', y: y(data.p90[last]), text: moneyCompact(data.p90[last]) },
        { key: 'p50', y: y(data.p50[last]), text: moneyCompact(data.p50[last]), strong: true },
        { key: 'p10', y: y(data.p10[last]), text: moneyCompact(data.p10[last]) },
    ]
}

function fanLabel(title: string, data: FanData, yearLabel: (y: number) => string): string {
    const last = data.years.length - 1
    return (
        `${title}. By ${yearLabel(data.years[last])} the median is ${money(data.p50[last])}; there is a 10% probability of ending ` +
        `below ${money(data.p10[last])} and a 10% probability of ending above ${money(data.p90[last])}. ` +
        'Use the arrow keys to read each year, or switch to the table.'
    )
}

function FanTable({ data, title, yearTitle }: { data: FanData; title: string; yearTitle: (y: number) => string }) {
    const cell = (k: Percentile) => (i: number) => money(data[k][i])
    const columns: Column<number>[] = [
        { key: 'year', label: 'Year', render: (i) => yearTitle(data.years[i]) },
        ...[...PERCENTILES].reverse().map((p) => ({ key: p.key, label: p.column, numeric: true, render: cell(p.key) })),
        ...(data.paidIn ? [{ key: 'paid', label: 'Paid in', numeric: true, render: (i: number) => money(data.paidIn?.[i]) }] : []),
    ]
    return <DataTable caption={title} columns={columns} rows={data.years.map((_, i) => i)} rowKey={(i) => i} />
}
