import { useAssetClassNames } from '@/api/names'
import type { Performance } from '@/api/schemas'
import { DataTable, FundCell, type Column } from '@/charts'
import { EMPTY, money, percentagePoints, signedMoney, signedPercent } from '@/lib/format'
import styles from '../Portfolio.module.css'
import { holdingGains, sumOf, type HoldingGain } from './model'

/** Gain or loss on each holding, and what it added to the whole portfolio's return. */
export function HoldingGains({ performance: p }: { performance: Performance }) {
    const names = useAssetClassNames()
    const rows = holdingGains(p)
    const [value, cost, gain] = [sumOf(rows, (r) => r.value), sumOf(rows, (r) => r.cost), sumOf(rows, (r) => r.gain)]
    const columns: Column<HoldingGain>[] = [
        { key: 'holding', label: 'Holding', render: (r) => <FundCell name={names(r.assetClass)} ticker={r.ticker} /> },
        { key: 'value', label: 'Value', numeric: true, render: (r) => money(r.value) },
        { key: 'cost', label: 'Cost', numeric: true, render: (r) => money(r.cost) },
        { key: 'gain', label: 'Gain or loss', numeric: true, render: (r) => signedMoney(r.gain) },
        { key: 'onCost', label: 'On its cost', numeric: true, render: (r) => (r.gainOnCost === null ? EMPTY : signedPercent(r.gainOnCost)) },
        { key: 'added', label: 'Added to return', numeric: true, render: (r) => (r.addedToReturn === null ? EMPTY : percentagePoints(r.addedToReturn)) },
    ]
    return (
        <section className={styles.subsection} aria-labelledby="gains-title">
            <h2 id="gains-title" className={styles.sectionTitle}>
                Gain or loss by holding
            </h2>
            <p className={styles.note}>
                Cost includes what was paid to trade. "Added to return" is each holding's gain as a share of all the money paid in; together they make the gain
                on what it holds now. Gains already taken by selling are listed under Activity.
            </p>
            <DataTable
                caption="Gain or loss by holding"
                stack
                columns={columns}
                rows={rows}
                rowKey={(r) => r.ticker}
                footer={[
                    'All holdings',
                    money(value),
                    money(cost),
                    signedMoney(gain),
                    cost > 0 ? signedPercent(gain / cost) : EMPTY,
                    p.net_contributions > 0 ? percentagePoints(gain / p.net_contributions) : EMPTY,
                ]}
            />
        </section>
    )
}
