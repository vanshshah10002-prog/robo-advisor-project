import { clsx } from 'clsx'
import { useState } from 'react'
import { useTrackRecord } from '@/api/queries'
import type { MonteCarlo, Performance, PortfolioDetail } from '@/api/schemas'
import { FanChart } from '@/charts'
import { money, percent } from '@/lib/format'
import { parseWhole } from '@/lib/parse'
import { nearestTested } from '@/lib/risk'
import { usePageTitle } from '@/lib/usePageTitle'
import { Button } from '@/ui/Button'
import { ChoiceGroup } from '@/ui/ChoiceGroup'
import { Field, TextInput } from '@/ui/Field'
import { MoneyField } from '@/ui/MoneyField'
import { Notice } from '@/ui/Notice'
import { Stat, StatGroup } from '@/ui/Stat'
import { sectionTitle, usePortfolio } from '../context'
import styles from '../Portfolio.module.css'
import { accuracyNote, lossSentence, MAX_YEARS, OUTLOOK_PATHS, outlookSentence, validYears, type OutlookInputs } from './model'
import { useOutlook } from './useOutlook'

const BASIS = [
    { value: 'real', label: "Today's money" },
    { value: 'nominal', label: 'Pounds of the day' },
] as const

/** Where the portfolio could go from here: a range, never a single line. */
export default function OutlookPage() {
    const { id, performance, detail } = usePortfolio()
    usePageTitle(sectionTitle(id, 'Outlook'))
    // Projecting before the monthly amount is known would understate every outcome.
    if (!detail) return <p className={styles.loading}>The outlook starts from this portfolio's monthly amount, so it waits for its details to load.</p>
    return <Outlook id={id} performance={performance} detail={detail} />
}

function Outlook({ id, performance, detail }: { id: number; performance: Performance; detail: PortfolioDetail }) {
    const { inputs, change, projection, invalid, catchingUp } = useOutlook(id, performance.total_value, detail.monthly_contribution)
    const mc = projection.data

    return (
        <article className={clsx(styles.section, 'stagger')} aria-labelledby="outlook-title" aria-busy={catchingUp || undefined}>
            <header className={styles.head}>
                <h1 id="outlook-title" className={styles.title}>
                    {mc ? outlookSentence(mc) : 'Simulating the years ahead'}
                </h1>
                <p className={styles.note} aria-live="polite">
                    {invalid ? 'These figures are for the last inputs that were valid. Correct the inputs to update them.' : ''}
                </p>
            </header>
            <Controls inputs={inputs} change={change} />
            {projection.isError && !mc && (
                <Notice tone="error" title="The outlook could not be simulated" action={<Button size="sm" variant="secondary" onClick={() => projection.refetch()}>Try again</Button>}>
                    {projection.error.message}
                </Notice>
            )}
            {mc && <Projection mc={mc} goal={inputs.goal} performance={performance} pending={catchingUp || projection.isFetching} />}
            {mc && <Reading mc={mc} risk={detail.risk_score} />}
        </article>
    )
}

function Controls({ inputs, change }: { inputs: OutlookInputs; change: (patch: Partial<OutlookInputs>) => void }) {
    // Null until edited, so the box follows the default horizon when the risk profile arrives after the first render.
    const [yearsText, setYearsText] = useState<string | null>(null)
    return (
        <section className={styles.controls} aria-label="What to simulate">
            <Field id="years" label="Years ahead" error={validYears(inputs.years) ? undefined : `Enter a whole number of years from 1 to ${MAX_YEARS}.`}>
                {(control) => (
                    <TextInput
                        {...control}
                        inputMode="numeric"
                        suffix="years"
                        value={yearsText ?? String(inputs.years ?? '')}
                        onChange={(e) => {
                            setYearsText(e.target.value)
                            change({ years: parseWhole(e.target.value) })
                        }}
                    />
                )}
            </Field>
            <MoneyField
                id="monthly"
                label="Added each month"
                hint="Optional. Leave empty for none."
                value={inputs.monthly || null}
                emptyValue={0}
                onChange={(monthly) => change({ monthly })}
                error={inputs.monthly === null || inputs.monthly < 0 ? 'Enter a monthly amount, or leave it empty.' : undefined}
            />
            <MoneyField
                id="goal"
                label="A goal"
                hint="Optional. The amount you are aiming for."
                value={inputs.goal}
                onChange={(goal) => change({ goal })}
            />
            <ChoiceGroup
                legend="Show amounts in"
                inline
                options={BASIS}
                value={inputs.realTerms ? 'real' : 'nominal'}
                onChange={(v) => change({ realTerms: v === 'real' })}
            />
        </section>
    )
}

function Projection({ mc, goal, performance: p, pending }: { mc: MonteCarlo; goal: number | null; performance: Performance; pending: boolean }) {
    const end = mc.years.length - 1
    const basis = mc.real_terms ? `in today's money, after ${percent(mc.inflation_rate ?? 0.025)} inflation a year` : 'in the pounds of the day'
    return (
        <>
            <StatGroup>
                <Stat
                    label="Middle outcome"
                    provenance="simulated"
                    value={money(mc.percentile_50[end])}
                    detail="Half of the outcomes land above it, half below"
                />
                <Stat label="Paid in by then" value={money(mc.contributions[end])} detail={mc.real_terms ? "In today's money" : undefined} />
                <Stat
                    label="Chance of ending below what was paid in"
                    provenance="simulated"
                    value={mc.probability_of_loss === null ? '—' : percent(mc.probability_of_loss, 0)}
                />
                {goal !== null && mc.probability_of_goal != null && (
                    <Stat label={`Chance of reaching ${money(goal)}`} provenance="simulated" value={percent(mc.probability_of_goal, 0)} />
                )}
            </StatGroup>
            <FanChart
                title={`What ${money(p.total_value)} could become`}
                summary={`The bands hold 8 in 10, and half, of ${OUTLOOK_PATHS.toLocaleString('en-GB')} simulated futures; the line is the middle one.`}
                data={{
                    years: mc.years,
                    p10: mc.percentile_10,
                    p25: mc.percentile_25,
                    p50: mc.percentile_50,
                    p75: mc.percentile_75,
                    p90: mc.percentile_90,
                    paidIn: mc.contributions,
                }}
                goal={goal}
                startYear={new Date().getFullYear()}
                pending={pending}
                notes={
                    `Simulated from the expected return (${percent(p.expected_return)} a year) and typical yearly swing (±${percent(p.expected_volatility)}) ` +
                    `stored when the portfolio was opened, with fat-tailed yearly returns, ${basis}. Before fund costs. Not a forecast.`
                }
            />
        </>
    )
}

/** How to read the fan: how the chance of a loss changes, and how often past forecasts held. */
function Reading({ mc, risk }: { mc: MonteCarlo; risk: number }) {
    const record = useTrackRecord(nearestTested(risk))
    const loss = lossSentence(mc)
    const accuracy = record.data ? accuracyNote(record.data) : null
    if (!loss && !accuracy) return null
    return (
        <section className={styles.subsection} aria-labelledby="reading-title">
            <h2 id="reading-title" className={styles.sectionTitle}>
                Reading the range
            </h2>
            {loss && <p className={styles.note}>{loss}</p>}
            {accuracy && <p className={styles.note}>{accuracy}</p>}
        </section>
    )
}
