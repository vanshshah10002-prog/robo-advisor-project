import { CheckCircle, Warning } from '@phosphor-icons/react'
import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { isNotFound } from '@/api/http'
import { useAssetClassNames, useFundNames } from '@/api/names'
import { usePerformance, usePortfolioDetail } from '@/api/queries'
import type { Performance } from '@/api/schemas'
import { AllocationBar, DriftBars } from '@/charts'
import { dateTime, money, signedMoney } from '@/lib/format'
import { sleeveOf } from '@/lib/palette'
import { level } from '@/lib/risk'
import { usePageTitle } from '@/lib/usePageTitle'
import { useIdentity } from '@/store/session'
import { Button, ButtonLink } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import { Delta, Stat, StatGroup } from '@/ui/Stat'
import { Tag } from '@/ui/Tag'
import NotFound from '../NotFound'
import { isUnrecorded, overviewSentence } from './model'
import styles from './Portfolio.module.css'

const parseId = (raw: string | undefined) => (raw && /^\d+$/.test(raw) ? Number(raw) : null)

/** One portfolio: what it is worth, what it holds, and how far it has drifted. */
export default function PortfolioPage() {
    const id = parseId(useParams().id)
    usePageTitle(id === null ? 'Page not found' : `Portfolio ${id}`)
    const setLastPortfolio = useIdentity((s) => s.setLastPortfolio)
    const performance = usePerformance(id)

    useEffect(() => {
        if (id !== null && performance.isSuccess) setLastPortfolio(id)
    }, [id, performance.isSuccess, setLastPortfolio])

    if (id === null) return <NotFound />
    if (performance.isPending) return <p className={styles.loading} aria-busy="true">Valuing the portfolio at the latest prices…</p>
    if (performance.isError) {
        if (isNotFound(performance.error)) return <Missing id={id} />
        return (
            <Notice tone="error" title="The portfolio could not be valued" action={<Button size="sm" variant="secondary" onClick={() => performance.refetch()}>Try again</Button>}>
                {performance.error.message}
            </Notice>
        )
    }
    return <Overview id={id} performance={performance.data} />
}

function Missing({ id }: { id: number }) {
    return (
        <div className={styles.page}>
            <h1 className={styles.title}>There is no portfolio {id}</h1>
            <p className={styles.lead}>It may have been opened in another browser, or the link is wrong.</p>
            <ButtonLink to="/portfolios">See your portfolios</ButtonLink>
        </div>
    )
}

function Overview({ id, performance: p }: { id: number; performance: Performance }) {
    const detail = usePortfolioDetail(id)
    const gain = p.total_value - p.net_contributions

    return (
        <article className={styles.page} aria-labelledby="portfolio-title">
            <header className={styles.head}>
                <p className="label">
                    Portfolio {id}
                    {detail.data && ` · risk level ${level(detail.data.risk_score)}${detail.data.uses_isa ? ' · ISA' : ''}`}
                </p>
                <h1 id="portfolio-title" className={styles.title}>
                    {isUnrecorded(p) ? `Portfolio ${id}` : overviewSentence(p)}
                </h1>
            </header>

            {isUnrecorded(p) ? (
                <Notice tone="info" title="This portfolio has no recorded purchases">
                    It was opened before purchases were recorded, so there is nothing to value or compare. Build a new portfolio to follow one
                    from the day it opens. <Link to="/start">Build a portfolio</Link>
                </Notice>
            ) : (
                <>
                    <StatGroup className={styles.stats}>
                        <Stat size="lg" label="Value" provenance="measured" value={money(p.total_value)} detail={p.valued_at ? `At closing prices, ${dateTime(p.valued_at)}` : undefined} />
                        <Stat label="Paid in" value={money(p.net_contributions)} />
                        <Stat label="Gain or loss" provenance="measured" value={signedMoney(gain)} detail={<Delta value={p.total_return_pct} />} />
                    </StatGroup>
                    <Status performance={p} />
                    <Holdings performance={p} />
                </>
            )}
            <p className={styles.back}>
                <Link to="/portfolios">All your portfolios</Link>
            </p>
        </article>
    )
}

function Status({ performance: p }: { performance: Performance }) {
    return (
        <div className={styles.status}>
            {p.needs_rebalance ? (
                <Tag tone="warn" icon={<Warning weight="bold" />}>Rebalance due</Tag>
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
                items={holdings.map((h) => ({ key: h.ticker, label: className(h.asset_class), detail: `${fundName(h.ticker)} · ${h.ticker}`, sleeve: sleeveOf(h.asset_class), weight: h.current_weight, value: h.current_value }))}
            />
            <DriftBars
                title="Distance from target"
                summary="How far each fund has moved from its target share. Outside its band, a rebalance brings it back."
                items={holdings.map((h) => ({ key: h.ticker, label: className(h.asset_class), detail: h.ticker, target: h.target_weight, current: h.current_price === null ? null : h.current_weight, band: h.band }))}
            />
        </>
    )
}
