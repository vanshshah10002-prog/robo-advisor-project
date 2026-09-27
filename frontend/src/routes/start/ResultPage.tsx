import { ArrowRight } from '@phosphor-icons/react'
import { clsx } from 'clsx'
import { Navigate } from 'react-router-dom'
import { isNotFound } from '@/api/http'
import { usePreview, useRiskProfile, useTrackRecord } from '@/api/queries'
import type { RiskProfile } from '@/api/schemas'
import { AllocationBar } from '@/charts'
import { sleeveTotals } from '@/charts/model'
import { date, money, percent } from '@/lib/format'
import { level } from '@/lib/risk'
import { usePageTitle } from '@/lib/usePageTitle'
import { useIdentity, useOnboardingDraft } from '@/store/session'
import { Button, ButtonLink } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import { Delta, Stat, StatGroup } from '@/ui/Stat'
import { Provenance } from '@/ui/Tag'
import { Term } from '@/ui/Term'
import styles from './Result.module.css'

/** Amount used to preview the mix when none was given; the split does not depend on it. */
const SPLIT_PREVIEW_AMOUNT = 10_000
const SHORT_HORIZON_YEARS = 5
const SHORT_HORIZON_CAP = 6

/** Step 4: the risk level, what sets it, what it holds and how far it has fallen before. */
export default function ResultPage() {
    usePageTitle('Your risk level')
    const userId = useIdentity((s) => s.userId)
    if (userId === null) return <Navigate to="/start" replace />
    return <Result userId={userId} />
}

function Result({ userId }: { userId: number }) {
    const profile = useRiskProfile(userId)
    if (profile.isPending) return <p className={styles.loading} aria-busy="true">Loading your risk level…</p>
    if (profile.isError) {
        if (isNotFound(profile.error)) return <Navigate to="/start" replace />
        return (
            <Notice tone="error" title="Your risk level did not load" action={<Button size="sm" variant="secondary" onClick={() => profile.refetch()}>Try again</Button>}>
                {profile.error.message}
            </Notice>
        )
    }
    return <Explained profile={profile.data} userId={userId} />
}

function Explained({ profile, userId }: { profile: RiskProfile; userId: number }) {
    const amount = useOnboardingDraft((s) => s.investmentAmount)
    return (
        <article className={clsx(styles.result, 'stagger')} aria-labelledby="result-title">
            <header className={styles.head}>
                <p className="label">Step 4 of 4</p>
                <h1 id="result-title" className={styles.title}>
                    Your risk level is <em>{level(profile.composite_score)}</em> out of 10
                </h1>
                <p className={styles.band}>{profile.risk_band}</p>
            </header>

            <StatGroup className={styles.stats}>
                <Stat label="Willingness to take risk" provenance="estimated" value={level(profile.subjective_score)} detail="From how you feel about losses" />
                <Stat label="Capacity for loss" provenance="estimated" value={level(profile.objective_score)} detail="From your finances and your time horizon" />
            </StatGroup>
            <p className={styles.explain}>
                Your level weighs the two, and leans to the lower one where they disagree: a portfolio should never ask you to
                bear more than you can afford, or more than you would put up with.
                {profile.time_horizon_years < SHORT_HORIZON_YEARS &&
                    ` Because you need the money within ${SHORT_HORIZON_YEARS} years, the level cannot go above ${SHORT_HORIZON_CAP}.`}
            </p>

            <SleeveSplit profile={profile} userId={userId} amount={amount ?? SPLIT_PREVIEW_AMOUNT} />
            <WorstFall assessed={profile.composite_score} tested={profile.risk_score_int} amount={amount} />

            <div className={styles.actions}>
                <ButtonLink to="/start" variant="quiet">
                    Change my answers
                </ButtonLink>
                <ButtonLink to="/proposal" trailingIcon={<ArrowRight weight="bold" />}>
                    See your proposal
                </ButtonLink>
            </div>
        </article>
    )
}

function SleeveSplit({ profile, userId, amount }: { profile: RiskProfile; userId: number; amount: number }) {
    const preview = usePreview({ user_id: userId, risk_score: profile.composite_score, investment_amount: amount, monthly_contribution: 0, uses_isa: profile.uses_isa })
    if (preview.isPending) {
        return (
            <p className={styles.loading} aria-busy="true">
                Working out the mix for your level. The first time takes about ten seconds.
            </p>
        )
    }
    if (preview.isError) return <Notice tone="warn" title="The mix for your level did not load">{preview.error.message}</Notice>

    const totals = sleeveTotals(preview.data.allocations)
    return (
        <AllocationBar
            title={`What level ${level(preview.data.risk_score)} holds`}
            summary="Growth holdings aim to grow over the years; defensive ones hold their value better when shares fall."
            provenance="estimated"
            items={[
                { key: 'growth', label: 'Growth', detail: 'Shares, property and gold', sleeve: 'growth', weight: totals.growth },
                { key: 'defensive', label: 'Defensive', detail: 'Bonds and cash-like funds', sleeve: 'defensive', weight: totals.defensive },
            ]}
        />
    )
}

/** The backtest covers whole levels only, so a level like 5.5 is shown by its nearest tested level, and says so. */
function WorstFall({ assessed, tested, amount }: { assessed: number; tested: number; amount: number | null }) {
    const record = useTrackRecord(tested)
    if (!record.isSuccess) return null
    const { strategy, start, end, calendar_years: years } = record.data
    const worstYear = years.filter((y) => !y.partial).reduce<(typeof years)[number] | null>((w, y) => (w === null || y.strategy < w.strategy ? y : w), null)

    return (
        <section className={styles.fall} aria-labelledby="fall-title">
            <h2 id="fall-title" className={styles.fallTitle}>
                How far level {tested} has fallen before <Provenance kind="simulated" />
            </h2>
            <StatGroup>
                <Stat label={<Term explain="maxDrawdown">Maximum drawdown</Term>} value={<Delta value={strategy.max_drawdown} />} detail={amount ? `About ${money(amount * strategy.max_drawdown)} on ${money(amount)}` : undefined} />
                {worstYear && <Stat label={`Worst calendar year, ${worstYear.year}`} value={<Delta value={worstYear.strategy} />} />}
            </StatGroup>
            <p className={styles.explain}>
                From a test on real London prices between {date(start)} and {date(end)}, building a level-{tested} portfolio
                {assessed !== tested && ` (the nearest tested level to your ${level(assessed)})`} with the same rules at each date, using only what
                was known on that date. Over the whole period it returned {percent(strategy.cagr)} a year. Past performance, real or simulated,
                is not a guide to what comes next.
            </p>
        </section>
    )
}
