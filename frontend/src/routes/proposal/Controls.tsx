import { useNavigate } from 'react-router-dom'
import { useCreatePortfolio } from '@/api/queries'
import type { PreviewRequest, RiskProfile } from '@/api/schemas'
import { level, levelStops } from '@/lib/risk'
import { useIdentity } from '@/store/session'
import { Button } from '@/ui/Button'
import { ChoiceGroup } from '@/ui/ChoiceGroup'
import { Notice } from '@/ui/Notice'
import { Slider } from '@/ui/Slider'
import { MoneyField } from '@/ui/MoneyField'
import type { ProposalInputs } from './useProposal'
import styles from './Proposal.module.css'

const ISA_OPTIONS = [
    { value: 'yes', label: 'ISA' },
    { value: 'no', label: 'General account' },
] as const

interface ControlsProps {
    profile: RiskProfile
    inputs: ProposalInputs
    change: (patch: Partial<ProposalInputs>) => void
}

/** What the investor can change: amounts, the account, and a risk level no higher than assessed. */
export function Controls({ profile, inputs, change }: ControlsProps) {
    const stops = levelStops(profile.composite_score)
    const assessed = stops[stops.length - 1]

    return (
        <section className={styles.controls} aria-labelledby="controls-title">
            <h2 id="controls-title" className={styles.sideTitle}>
                Adjust
            </h2>
            <MoneyField
                id="amount"
                label="Amount to invest now"
                value={inputs.amount}
                onChange={(amount) => change({ amount })}
                error={inputs.amount === null || inputs.amount <= 0 ? 'Enter an amount above £0.' : undefined}
            />
            <MoneyField
                id="monthly"
                label="Each month"
                hint="Optional. Leave empty for none."
                value={inputs.monthly || null}
                emptyValue={0}
                onChange={(monthly) => change({ monthly })}
                error={inputs.monthly === null || inputs.monthly < 0 ? 'Enter a monthly amount, or leave it empty.' : undefined}
            />
            <ChoiceGroup
                id="isa"
                legend="Account"
                inline
                options={ISA_OPTIONS}
                value={inputs.usesIsa ? 'yes' : 'no'}
                onChange={(v) => change({ usesIsa: v === 'yes' })}
            />
            <Slider
                id="risk"
                label="Risk level"
                hint={`Your answers put you at ${level(assessed)}. You can take less risk than that, not more.`}
                stops={stops}
                value={inputs.risk}
                format={level}
                describe={(v) => `Level ${level(v)} of 10${v === assessed ? ', your assessed level' : ''}`}
                onChange={(risk) => change({ risk })}
            />
        </section>
    )
}

interface OpenPanelProps {
    userId: number
    built: PreviewRequest | null
    ready: boolean
}

/**
 * The one action on the page. It opens exactly the portfolio on screen:
 * the request the shown preview was built from, and only once it is current.
 */
export function OpenPanel({ userId, built, ready }: OpenPanelProps) {
    const navigate = useNavigate()
    const setLastPortfolio = useIdentity((s) => s.setLastPortfolio)
    const create = useCreatePortfolio()

    const open = () => {
        if (!built || !ready) return
        create.mutate(
            { ...built, user_id: userId },
            {
                onSuccess: (portfolio) => {
                    setLastPortfolio(portfolio.portfolio_id)
                    navigate(`/portfolio/${portfolio.portfolio_id}`)
                },
            },
        )
    }

    return (
        <section className={styles.open} aria-labelledby="open-title">
            <h2 id="open-title" className="visually-hidden">
                Open this portfolio
            </h2>
            <p className={styles.openNote}>
                Opening records a purchase of each fund at the latest closing prices, so you can follow it from today. No real money
                moves.
            </p>
            <Button className={styles.openButton} onClick={open} disabled={!ready} loading={create.isPending}>
                Open portfolio
            </Button>
            {create.isError && (
                <Notice tone="error" title="The portfolio was not opened">
                    {create.error.message} Nothing was saved; try again.
                </Notice>
            )}
        </section>
    )
}
