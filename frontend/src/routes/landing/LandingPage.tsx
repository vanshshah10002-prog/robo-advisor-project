import { ArrowRight } from '@phosphor-icons/react'
import { useState } from 'react'
import { useTrackRecord } from '@/api/queries'
import { usePageTitle } from '@/lib/usePageTitle'
import { useIdentity } from '@/store/session'
import { ButtonLink } from '@/ui/Button'
import { ChoiceGroup } from '@/ui/ChoiceGroup'
import { TrackRecordChart } from '../TrackRecordChart'
import { trackRecordSentence } from './evidence'
import styles from './Landing.module.css'

const STEPS = [
    {
        title: 'Tell us about you',
        body: 'Your goal, how you feel when prices fall, and what you could afford to lose. About five minutes; rough figures are fine.',
    },
    {
        title: 'See it before it is saved',
        body: 'The exact funds, what they cost in pounds a year, and a range of where the money could be, from bad years to good.',
    },
    {
        title: 'Follow it in plain figures',
        body: 'What it is worth at the latest prices, what you have paid in, and when it has drifted far enough to rebalance.',
    },
] as const

const LEVELS = [3, 5, 7, 9] as const
const DEFAULT_LEVEL = 5

/** The front page: what this does, how, and how its rules have done, told straight. */
export default function LandingPage() {
    usePageTitle()
    const lastPortfolioId = useIdentity((s) => s.lastPortfolioId)

    return (
        <article className={styles.page}>
            <header className={styles.hero}>
                <p className="label">Model portfolios for UK investors</p>
                <h1 className={styles.title}>
                    A portfolio you can <em>read</em>.
                </h1>
                <p className={styles.lead}>
                    Answer a few questions. See the exact portfolio, its costs and a range of outcomes before anything is saved. Then follow it
                    in plain figures, each one saying where it came from.
                </p>
                <div className={styles.actions}>
                    <ButtonLink to="/start" trailingIcon={<ArrowRight weight="bold" />}>
                        Build a portfolio
                    </ButtonLink>
                    {lastPortfolioId !== null && (
                        <ButtonLink to={`/portfolio/${lastPortfolioId}`} variant="secondary">
                            Go to your portfolio
                        </ButtonLink>
                    )}
                </div>
            </header>

            <section className={styles.steps} aria-labelledby="how-title">
                <h2 id="how-title" className={styles.sectionTitle}>
                    How it works
                </h2>
                <ol>
                    {STEPS.map((step) => (
                        <li key={step.title}>
                            <h3>{step.title}</h3>
                            <p>{step.body}</p>
                        </li>
                    ))}
                </ol>
            </section>

            <Evidence />
        </article>
    )
}

function Evidence() {
    const [risk, setRisk] = useState<number>(DEFAULT_LEVEL)
    const record = useTrackRecord(risk)

    return (
        <section className={styles.evidence} aria-labelledby="evidence-title">
            <div className={styles.evidenceHead}>
                <h2 id="evidence-title" className={styles.sectionTitle}>
                    How the rules have done
                </h2>
                <p className={styles.sentence}>{record.data ? trackRecordSentence(record.data) : ' '}</p>
                <ChoiceGroup
                    legend="Risk level shown"
                    inline
                    options={LEVELS.map((l) => ({ value: l, label: `Level ${l}` }))}
                    value={risk}
                    onChange={setRisk}
                    className={styles.levels}
                />
            </div>
            <TrackRecordChart record={record} />
        </section>
    )
}
