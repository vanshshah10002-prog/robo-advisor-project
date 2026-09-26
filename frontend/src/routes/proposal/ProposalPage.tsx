import { Navigate } from 'react-router-dom'
import { isNotFound } from '@/api/http'
import { useAssetClassNames } from '@/api/names'
import { useRiskProfile } from '@/api/queries'
import type { MonteCarlo, Preview, PreviewRequest, RiskProfile } from '@/api/schemas'
import { AllocationBar, DataTable, FanChart, FundCell, type Column } from '@/charts'
import { money, percent } from '@/lib/format'
import { usePageTitle } from '@/lib/usePageTitle'
import { Button } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import { Stat, StatGroup } from '@/ui/Stat'
import { useIdentity } from '@/store/session'
import { Controls, OpenPanel } from './Controls'
import { proposalSentence } from './model'
import { useProposal } from './useProposal'
import styles from './Proposal.module.css'

type Allocation = Preview['allocations'][number]

/** The proposal: a portfolio built for you, shown in full before anything is saved. */
export default function ProposalPage() {
    usePageTitle('Your proposal')
    const userId = useIdentity((s) => s.userId)
    const profile = useRiskProfile(userId)
    if (userId === null) return <Navigate to="/start" replace />
    if (profile.isPending) return <p className={styles.loading} aria-busy="true">Loading your risk level…</p>
    if (profile.isError) {
        if (isNotFound(profile.error)) return <Navigate to="/start" replace />
        return (
            <Notice tone="error" title="Your risk level did not load" action={<Button size="sm" variant="secondary" onClick={() => profile.refetch()}>Try again</Button>}>
                {profile.error.message}
            </Notice>
        )
    }
    return <Proposal profile={profile.data} userId={userId} />
}

function Proposal({ profile, userId }: { profile: RiskProfile; userId: number }) {
    const { inputs, change, settled, preview, projection, current, catchingUp, invalid } = useProposal(profile, userId)
    const stale = catchingUp || invalid

    return (
        <div className={styles.layout}>
            {/* Outside the article so that on a phone the sentence comes before the controls. */}
            <header className={styles.head}>
                <p className="label">Your proposal · not saved</p>
                <h1 id="proposal-title" className={styles.title}>
                    {headline(preview.data, settled, invalid)}
                </h1>
                <p className={styles.status} aria-live="polite">
                    {statusLine(preview.data !== undefined, catchingUp, invalid)}
                </p>
            </header>
            <div className={styles.side}>
                <Controls profile={profile} inputs={inputs} change={change} />
                <OpenPanel userId={userId} built={settled} ready={current} />
            </div>
            <article className={styles.content} aria-labelledby="proposal-title" aria-busy={catchingUp || undefined}>
                {preview.isError && !preview.data && (
                    <Notice tone="error" title="The proposal could not be built" action={<Button size="sm" variant="secondary" onClick={() => preview.refetch()}>Try again</Button>}>
                        {preview.error.message}
                    </Notice>
                )}
                {preview.data && <Figures preview={preview.data} projection={projection.data} years={profile.time_horizon_years} pending={stale} />}
                {preview.data && settled && (
                    <Projection projection={projection.data} pending={stale || projection.isFetching} amount={settled.investment_amount} />
                )}
            </article>
        </div>
    )
}

function headline(preview: Preview | undefined, built: PreviewRequest | null, invalid: boolean): string {
    if (preview && built) return proposalSentence(preview, built.investment_amount, built.monthly_contribution)
    return invalid ? 'Enter an amount to see your proposal' : 'Building your portfolio'
}

function statusLine(shown: boolean, catchingUp: boolean, invalid: boolean): string {
    if (invalid && shown) return 'These figures are for the last amounts that were valid. Correct the amounts to update them.'
    if (catchingUp) return 'Rebuilding for your changes. A level not built recently takes about ten seconds.'
    return ''
}

function Figures({ preview, projection, years, pending }: { preview: Preview; projection?: MonteCarlo; years: number; pending: boolean }) {
    const names = useAssetClassNames()
    const allocation = preview.allocations.map((a) => ({
        key: a.ticker,
        label: names(a.asset_class),
        detail: a.ticker,
        sleeve: a.sleeve,
        weight: a.weight,
        value: a.amount_gbp,
    }))

    return (
        <>
            <StatGroup className={styles.stats}>
                <Stat label="Expected return" provenance="estimated" value={percent(preview.expected_annual_return)} detail="A year, on average, before inflation" />
                <Stat label="Typical yearly swing" provenance="estimated" value={`±${percent(preview.expected_volatility)}`} detail="Two years in three land within this of the average" />
                <Stat label="Fund costs" value={money(preview.annual_fund_cost_gbp)} detail={`A year: ${percent(preview.total_expense_ratio, 2)} of the amount`} />
                <Stat
                    label="Chance of ending below what you paid in"
                    provenance="simulated"
                    value={projection?.probability_of_loss == null ? '…' : percent(projection.probability_of_loss, 0)}
                    detail={`After ${years} year${years === 1 ? '' : 's'}, in today's money`}
                />
            </StatGroup>
            <AllocationBar
                title="What it would hold"
                summary="Each fund's share, growth first. Hover or use the arrow keys to read one."
                provenance="estimated"
                items={allocation}
                pending={pending}
            />
            <FundsTable allocations={preview.allocations} names={names} />
        </>
    )
}

function Projection({ projection, pending, amount }: { projection?: MonteCarlo; pending: boolean; amount: number }) {
    if (!projection) return <p className={styles.loading} aria-busy="true">Simulating the years ahead…</p>
    return (
        <FanChart
            title={`What ${money(amount)} could become`}
            summary="In today's money. The bands hold 8 in 10, and half, of 2,000 simulated futures; the line is the middle one."
            data={{
                years: projection.years,
                p10: projection.percentile_10,
                p25: projection.percentile_25,
                p50: projection.percentile_50,
                p75: projection.percentile_75,
                p90: projection.percentile_90,
                paidIn: projection.contributions,
            }}
            startYear={new Date().getFullYear()}
            pending={pending}
            notes={`Simulated from the expected return and swing above, with fat-tailed yearly returns, after ${percent(projection.inflation_rate ?? 0.025)} inflation a year. Before fund costs. Not a forecast.`}
        />
    )
}

function FundsTable({ allocations, names }: { allocations: readonly Allocation[]; names: (id: string) => string }) {
    const columns: Column<Allocation>[] = [
        // What each fund holds sits under its name, so the table keeps to four columns on a phone.
        { key: 'fund', label: 'Fund', render: (a) => <FundCell name={a.etf_name} ticker={`${a.ticker} · ${names(a.asset_class)}`} /> },
        { key: 'share', label: 'Share', numeric: true, render: (a) => percent(a.weight) },
        { key: 'amount', label: 'Amount', numeric: true, render: (a) => money(a.amount_gbp) },
        { key: 'cost', label: 'Yearly cost', numeric: true, render: (a) => percent(a.expense_ratio, 2) },
    ]
    return (
        <section className={styles.funds} aria-labelledby="funds-title">
            <h2 id="funds-title" className={styles.sectionTitle}>
                The funds
            </h2>
            <DataTable caption="The funds in this proposal" columns={columns} rows={[...allocations].sort((a, b) => b.weight - a.weight)} rowKey={(a) => a.ticker} />
        </section>
    )
}
