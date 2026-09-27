import { ArrowsClockwise, CheckCircle, Warning } from '@phosphor-icons/react'
import { clsx } from 'clsx'
import { Link } from 'react-router-dom'
import { useAssetClassNames, useFundNames } from '@/api/names'
import { useRefreshPortfolio } from '@/api/queries'
import type { Performance } from '@/api/schemas'
import { AllocationBar, DriftBars } from '@/charts'
import { dateTime, money, signedMoney } from '@/lib/format'
import { usePageTitle } from '@/lib/usePageTitle'
import { Button } from '@/ui/Button'
import { CountUp } from '@/ui/CountUp'
import { Notice } from '@/ui/Notice'
import { Delta, Stat, StatGroup } from '@/ui/Stat'
import { Tag } from '@/ui/Tag'
import { sectionTitle, usePortfolio } from '../context'
import { overviewSentence } from '../model'
import styles from '../Portfolio.module.css'

/** What it is worth, against what went in, and whether anything needs doing. */
export default function OverviewPage() {
    const { id, performance: p } = usePortfolio()
    usePageTitle(sectionTitle(id))
    const gain = p.total_value - p.net_contributions

    return (
        <article className={clsx(styles.section, 'stagger')} aria-labelledby="overview-title">
            <h1 id="overview-title" className={styles.title}>
                {overviewSentence(p)}
            </h1>
            <div className={styles.subsection}>
                <StatGroup className={styles.stats}>
                    <Stat size="lg" label="Value" provenance="measured" value={<CountUp value={p.total_value} format={money} />} detail={p.valued_at ? `At closing prices, ${dateTime(p.valued_at)}` : undefined} />
                    <Stat label="Paid in" value={money(p.net_contributions)} />
                    <Stat label="Gain or loss" provenance="measured" value={signedMoney(gain)} detail={<Delta value={p.total_return_pct} />} />
                </StatGroup>
                <UpdatePrices id={id} />
            </div>
            <Status id={id} performance={p} />
            <Holdings performance={p} />
        </article>
    )
}

/** Values use the prices stored at the last update; this fetches the latest closes. */
function UpdatePrices({ id }: { id: number }) {
    const refresh = useRefreshPortfolio(id)
    return (
        <div className={styles.actions}>
            <Button size="sm" variant="secondary" leadingIcon={<ArrowsClockwise weight="bold" />} loading={refresh.isPending} onClick={() => refresh.mutate(undefined)}>
                Update prices
            </Button>
            <p className={styles.note} aria-live="polite">
                {refresh.isSuccess && `Updated to the closes of ${dateTime(refresh.data.valued_at)}.`}
            </p>
            {refresh.isError && (
                <Notice tone="error" title="The prices were not updated">
                    {refresh.error.message} The figures above are unchanged.
                </Notice>
            )}
        </div>
    )
}

function Status({ id, performance: p }: { id: number; performance: Performance }) {
    return (
        <div className={styles.status}>
            {p.needs_rebalance ? (
                <>
                    <Tag tone="warn" icon={<Warning weight="bold" />}>Rebalance due</Tag>
                    <p className={styles.note}>
                        Some holdings have drifted outside their bands. <Link to={`/portfolio/${id}/activity`}>Review the trades</Link> before
                        anything is sold or bought.
                    </p>
                </>
            ) : (
                <Tag tone="ok" icon={<CheckCircle weight="bold" />}>Within its bands</Tag>
            )}
            {p.unpriced_tickers.length > 0 && (
                <Notice tone="warn" title={`No recent price for ${p.unpriced_tickers.join(', ')}`}>
                    Their value is left out of the total until a price arrives.
                </Notice>
            )}
        </div>
    )
}

function Holdings({ performance: p }: { performance: Performance }) {
    const className = useAssetClassNames()
    const fundName = useFundNames()
    const holdings = [...p.holdings].sort((a, b) => b.current_value - a.current_value)
    return (
        <>
            <AllocationBar
                title="What it holds now"
                summary="Each fund's share of the value today, growth first."
                provenance="measured"
                items={holdings.map((h) => ({ key: h.ticker, label: className(h.asset_class), detail: `${fundName(h.ticker)} · ${h.ticker}`, sleeve: h.sleeve, weight: h.current_weight, value: h.current_value }))}
            />
            <DriftBars
                title="Distance from target"
                summary="How far each fund has moved from its target share. Outside its band, a rebalance brings it back."
                items={holdings.map((h) => ({ key: h.ticker, label: className(h.asset_class), detail: h.ticker, target: h.target_weight, current: h.current_price === null ? null : h.current_weight, band: h.band }))}
            />
        </>
    )
}

