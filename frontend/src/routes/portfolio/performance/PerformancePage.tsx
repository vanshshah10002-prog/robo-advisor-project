import { useState } from 'react'
import { useHistory } from '@/api/queries'
import type { History, Performance } from '@/api/schemas'
import { DataTable, LineChart, type Column } from '@/charts'
import { EMPTY, date, money, moneyCompact, percent, signedMoney, signedPercent } from '@/lib/format'
import { CATEGORICAL, CHART_INK } from '@/lib/palette'
import { usePageTitle } from '@/lib/usePageTitle'
import { Button } from '@/ui/Button'
import { ChoiceGroup } from '@/ui/ChoiceGroup'
import { Notice } from '@/ui/Notice'
import { Stat, StatGroup } from '@/ui/Stat'
import { sectionTitle, usePortfolio } from '../context'
import styles from '../Portfolio.module.css'
import { HoldingGains } from './HoldingGains'
import { annualised, availablePeriods, drawdowns, PERIODS, performanceSentence, periodReturn, pointsFor, worstFall, type Period } from './model'
import { TrackRecord } from './TrackRecord'

type Point = History['points'][number]

/** How the portfolio has done: its own measured record, then the strategy's simulated one. */
export default function PerformancePage() {
    const { id, performance, detail } = usePortfolio()
    usePageTitle(sectionTitle(id, 'Performance'))
    const history = useHistory(id)

    if (history.isPending) return <p className={styles.loading} aria-busy="true">Replaying the ledger against daily prices…</p>
    if (history.isError) {
        return (
            <Notice tone="error" title="The history did not load" action={<Button size="sm" variant="secondary" onClick={() => history.refetch()}>Try again</Button>}>
                {history.error.message}
            </Notice>
        )
    }
    return (
        <article className={styles.section} aria-labelledby="performance-title">
            <h1 id="performance-title" className={styles.title}>
                {performanceSentence(history.data)}
            </h1>
            <Figures points={history.data.points} performance={performance} />
            {history.data.unpriced_tickers.length > 0 && (
                <Notice tone="warn" title={`Some days have no price for ${history.data.unpriced_tickers.join(', ')}`}>
                    Those days are left out rather than filled in.
                </Notice>
            )}
            <Charts points={history.data.points} />
            <HoldingGains performance={performance} />
            <TrackRecord risk={detail?.risk_score ?? null} />
        </article>
    )
}

function Figures({ points, performance: p }: { points: readonly Point[]; performance: Performance }) {
    const sinceOpening = periodReturn(points, 'all')
    const fall = worstFall(points)
    const [first, last] = [points[0], points[points.length - 1]]
    const yearly = first && last ? annualised(last.cumulative_return, first.date, last.date) : null
    return (
        <StatGroup>
            <Stat label="Return since opening" provenance="measured" value={signedPercent(sinceOpening)} detail="Growth only: money paid in is not counted as gain" />
            <Stat label="Gain or loss" provenance="measured" value={signedMoney(p.total_value - p.net_contributions)} detail={`On ${money(p.net_contributions)} paid in`} />
            <Stat label="Worst fall from a high" provenance="measured" value={fall ? percent(-fall.value) : 'None yet'} detail={fall ? `Lowest on ${date(fall.date)}` : undefined} />
            <Stat
                label="Expected when opened"
                provenance="estimated"
                value={p.expected_return === null ? EMPTY : `${percent(p.expected_return)} a year`}
                detail={yearly === null ? 'Too soon to compare: that takes a year of history' : `Realised so far: ${signedPercent(yearly)} a year`}
            />
        </StatGroup>
    )
}

function Charts({ points }: { points: readonly Point[] }) {
    const periods = availablePeriods(points)
    const [chosen, setChosen] = useState<Period>('all')
    const period = periods.includes(chosen) ? chosen : 'all'
    const span = pointsFor(points, period) ?? points
    const label = PERIODS.find((p) => p.value === period)?.label.toLowerCase() ?? ''
    const empty = span.length < 2 ? `The charts start once two days of values are recorded${points[0] ? `; the first was ${date(points[0].date)}` : ''}.` : undefined

    return (
        <section className={styles.subsection} aria-labelledby="value-title">
            <h2 id="value-title" className={styles.sectionTitle}>
                Value over time
            </h2>
            {periods.length > 1 && (
                <ChoiceGroup legend="Period" inline options={PERIODS.filter((p) => periods.includes(p.value))} value={period} onChange={setChosen} />
            )}
            <LineChart
                title="Value and money paid in"
                summary={span.length >= 2 ? `Over ${label === 'since opening' ? 'the time since opening' : `the last ${label}`}, the value went from ${money(span[0].value)} to ${money(span[span.length - 1].value)}.` : undefined}
                provenance="measured"
                dates={span.map((p) => p.date)}
                series={[
                    { key: 'value', label: 'Value', colour: CATEGORICAL[0], values: span.map((p) => p.value), variant: 'area' },
                    { key: 'paid', label: 'Paid in', colour: CHART_INK.axis, values: span.map((p) => p.net_contributions), variant: 'reference' },
                ]}
                format={(v) => money(v)}
                axisFormat={moneyCompact}
                empty={empty}
            />
            {!empty && (
                <LineChart
                    title="How far below its high"
                    summary="Each day's time-weighted value against the highest it had reached; zero is a new high."
                    provenance="measured"
                    dates={span.map((p) => p.date)}
                    series={[{ key: 'fall', label: 'Below its high', colour: CATEGORICAL[3], values: drawdowns(span), variant: 'area' }]}
                    format={(v) => percent(v)}
                    height={180}
                />
            )}
            <PeriodReturns points={points} />
        </section>
    )
}

interface PeriodRow {
    key: string
    label: string
    value: number | null
}

const PERIOD_COLUMNS: Column<PeriodRow>[] = [
    { key: 'period', label: 'Period', render: (r) => r.label },
    { key: 'return', label: 'Return, time-weighted', numeric: true, render: (r) => (r.value === null ? 'Not open that long' : signedPercent(r.value)) },
]

function PeriodReturns({ points }: { points: readonly Point[] }) {
    const [first, last] = [points[0], points[points.length - 1]]
    const yearly = first && last ? annualised(last.cumulative_return, first.date, last.date) : null
    const rows: PeriodRow[] = [
        ...PERIODS.map((p) => ({ key: p.value, label: p.label, value: periodReturn(points, p.value) })),
        ...(yearly === null ? [] : [{ key: 'yearly', label: 'A year, on average', value: yearly }]),
    ]
    return <DataTable caption="Returns by period" columns={PERIOD_COLUMNS} rows={rows} rowKey={(r) => r.key} />
}

