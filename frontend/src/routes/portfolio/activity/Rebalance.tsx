import { useExecuteRebalance, useRebalancePlan } from '@/api/queries'
import type { RebalancePlan, RebalanceTrade } from '@/api/schemas'
import { DataTable, FundCell, type Column } from '@/charts'
import { money, percent, signedMoney } from '@/lib/format'
import { Button } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import styles from '../Portfolio.module.css'
import { pounds, rebalanceSentence } from './model'

const COLUMNS: Column<RebalanceTrade>[] = [
    { key: 'fund', label: 'Fund', render: (t) => <FundCell name={t.etf_name} ticker={t.ticker} /> },
    { key: 'action', label: 'Trade', render: (t) => (t.action === 'sell' ? 'Sell' : 'Buy') },
    { key: 'weights', label: 'Share now → target', numeric: true, render: (t) => `${percent(t.current_weight)} → ${percent(t.target_weight)}` },
    { key: 'value', label: 'Value', numeric: true, render: (t) => money(t.trade_value_gbp) },
    { key: 'cost', label: 'Cost', numeric: true, render: (t) => pounds(t.est_cost_gbp) },
    { key: 'gain', label: 'Gain realised', numeric: true, render: (t) => (t.action === 'sell' ? signedMoney(t.est_realised_gain_gbp) : '—') },
]

/**
 * Checks each holding against its band and, when a rebalance is due, shows
 * every trade with its cost and any gain it realises before anything runs.
 */
export function Rebalance({ id }: { id: number }) {
    const plan = useRebalancePlan(id)
    const execute = useExecuteRebalance(id)
    const done = execute.data?.executed ? execute.data : null

    return (
        <section className={styles.panel} aria-labelledby="rebalance-title">
            <h2 id="rebalance-title" className={styles.sectionTitle}>
                Rebalance
            </h2>
            {plan.isPending && <p className={styles.loading} aria-busy="true">Checking each holding against its target at the latest prices…</p>}
            {plan.isError && (
                <Notice tone="error" title="The check did not run" action={<Button size="sm" variant="secondary" onClick={() => plan.refetch()}>Try again</Button>}>
                    {plan.error.message}
                </Notice>
            )}
            {plan.data && <Plan plan={plan.data} onRun={() => execute.mutate(undefined)} running={execute.isPending} />}
            <p className={styles.note} aria-live="polite">
                {done && `Rebalanced: ${done.trades.length} trade${done.trades.length === 1 ? '' : 's'}, for about ${pounds(done.est_total_cost_gbp)} in costs.`}
            </p>
            {execute.isError && (
                <Notice tone="error" title="The rebalance did not run">
                    {execute.error.message} Nothing was traded.
                </Notice>
            )}
        </section>
    )
}

function Plan({ plan, onRun, running }: { plan: RebalancePlan; onRun: () => void; running: boolean }) {
    const runnable = plan.needs_rebalance && plan.trades.length > 0
    return (
        <>
            <p className={styles.note}>{rebalanceSentence(plan)}</p>
            {plan.stale_tickers.length > 0 && (
                <Notice tone="warn" title={`Old prices for ${plan.stale_tickers.join(', ')}`}>
                    Update the prices before rebalancing, so the trades are sized on today's values.
                </Notice>
            )}
            {runnable && (
                <>
                    <DataTable
                        caption="The trades a rebalance would make"
                        stack
                        columns={COLUMNS}
                        rows={plan.trades}
                        rowKey={(t) => t.ticker}
                        footer={['All trades', '', '', '', pounds(plan.est_total_cost_gbp), signedMoney(plan.est_realised_gain_gbp)]}
                    />
                    <div className={styles.actions}>
                        <Button onClick={onRun} loading={running}>
                            Rebalance now
                        </Button>
                        <p className={styles.note}>Sells and buys at the latest closing prices. Model portfolio: no real money moves.</p>
                    </div>
                </>
            )}
        </>
    )
}
