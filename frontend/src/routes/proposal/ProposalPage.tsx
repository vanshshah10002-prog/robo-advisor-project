import { clsx } from 'clsx'
import { Navigate } from 'react-router-dom'
import { isNotFound } from '@/api/http'
import { useAssetClassNames } from '@/api/names'
import { useRiskProfile } from '@/api/queries'
import type { MonteCarlo, Preview, PreviewRequest, RiskProfile } from '@/api/schemas'
import { AllocationBar, DataTable, FanChart, FundCell, type Column } from '@/charts'
import { decimal, money, percent } from '@/lib/format'
import { usePageTitle } from '@/lib/usePageTitle'
import { Button } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import { Stat, StatGroup } from '@/ui/Stat'
import { Term } from '@/ui/Term'
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
        <div className={clsx(styles.layout, 'stagger')}>
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
            <ProposalStats preview={preview} projection={projection} years={years} />
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

function ProposalStats({ preview, projection, years }: { preview: Preview; projection?: MonteCarlo; years: number }) {
    const rf = preview.risk_free_rate
    return (
        <StatGroup className={styles.stats}>
            <Stat
                label={<Term explain="expectedReturn">Expected return</Term>}
                provenance="estimated"
                value={percent(preview.expected_annual_return)}
                detail="A year, on average, before inflation"
            />
            <Stat
                label={<Term explain="volatility">Volatility</Term>}
                provenance="estimated"
                value={percent(preview.expected_volatility)}
                detail="Standard deviation of yearly returns"
            />
            <Stat
                label={<Term explain="sharpe">Sharpe ratio</Term>}
                provenance="estimated"
                value={decimal(preview.sharpe_ratio, 2)}
                detail={rf === null ? undefined : `Against a ${percent(rf)} risk-free rate`}
            />
            <Stat
                label={<Term explain="ongoingCharges">Ongoing charges</Term>}
                value={money(preview.annual_fund_cost_gbp)}
                detail={`A year: ${percent(preview.total_expense_ratio, 2)} of the amount`}
            />
            <Stat
                label={<Term explain="lossProbability">Probability of a loss</Term>}
                provenance="simulated"
                value={projection?.probability_of_loss == null ? '…' : percent(projection.probability_of_loss, 0)}
                detail={`Below the amount paid in after ${years} year${years === 1 ? '' : 's'}, adjusted for inflation`}
            />
        </StatGroup>
    )
}

function Projection({ projection, pending, amount }: { projection?: MonteCarlo; pending: boolean; amount: number }) {
    if (!projection) return <p className={styles.loading} aria-busy="true">Simulating the years ahead…</p>
    return (
        <FanChart
            title={`What ${money(amount)} could become`}
            summary="Adjusted for inflation. The shaded bands are the 50% and 80% probability ranges of 2,000 simulated paths; the line is the median."
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
            notes={
                `Simulated from the expected return and volatility above, with fat-tailed yearly returns, adjusted for ` +
                `${percent(projection.inflation_rate ?? 0.025)} inflation a year. After fund charges. Not a forecast.`
            }
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
