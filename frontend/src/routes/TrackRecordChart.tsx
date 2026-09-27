import type { UseQueryResult } from '@tanstack/react-query'
import type { TrackRecord } from '@/api/schemas'
import { LineChart } from '@/charts'
import { money, moneyCompact } from '@/lib/format'
import { CATEGORICAL } from '@/lib/palette'
import { benchmarkLabel, benchmarkNames } from './landing/evidence'
import styles from './TrackRecordChart.module.css'

/**
 * The walk-forward backtest week by week, against a benchmark named by its
 * funds, with its assumptions and biases underneath. Shared by the front
 * page and the portfolio's Performance section, so both say exactly the
 * same thing.
 */
export function TrackRecordChart({ record }: { record: UseQueryResult<TrackRecord> }) {
    const data = record.data
    return (
        <LineChart
            title={data ? `${money(data.initial)} at risk level ${data.risk}, week by week` : 'The walk-forward backtest'}
            summary={
                data
                    ? `This strategy’s backtest against a benchmark of ${benchmarkNames(data)}, with the same share in shares and rebalanced the same way.`
                    : undefined
            }
            provenance="simulated"
            pending={record.isFetching}
            empty={record.isError ? `The test results did not load: ${record.error.message}` : record.isPending ? 'Loading the test results…' : undefined}
            dates={data?.series.map((p) => p.date) ?? []}
            series={[
                { key: 'strategy', label: 'This strategy (backtest)', colour: CATEGORICAL[0], values: data?.series.map((p) => p.strategy) ?? [] },
                { key: 'benchmark', label: data ? benchmarkLabel(data) : 'Benchmark', colour: CATEGORICAL[1], values: data?.series.map((p) => p.benchmark) ?? [] },
            ]}
            baseline={data ? { value: data.initial, label: `${money(data.initial)} invested` } : undefined}
            format={(v) => money(v)}
            axisFormat={moneyCompact}
            notes={
                data && (
                    <ul className={styles.notes}>
                        {data.notes.map((n) => (
                            <li key={n}>{n}</li>
                        ))}
                    </ul>
                )
            }
        />
    )
}
