import { useState } from 'react'
import { useMonteCarlo, usePreview } from '@/api/queries'
import type { PreviewRequest, RiskProfile } from '@/api/schemas'
import { clampLevel } from '@/lib/risk'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { useOnboardingDraft } from '@/store/session'
import { projectionRequest } from './model'

/** Long enough to let a slider drag or a typed amount settle before rebuilding. */
const SETTLE_MS = 450

export interface ProposalInputs {
    amount: number | null
    monthly: number | null
    usesIsa: boolean
    risk: number
}

/** The preview request the inputs ask for, or null while an amount is not a valid figure. */
function toRequest({ amount, monthly, risk, usesIsa }: ProposalInputs, userId: number): PreviewRequest | null {
    if (typeof amount !== 'number' || amount <= 0 || typeof monthly !== 'number' || monthly < 0) return null
    return { user_id: userId, risk_score: risk, investment_amount: amount, monthly_contribution: monthly, uses_isa: usesIsa }
}

/**
 * Everything the proposal page shows, in one place:
 * - inputs start from the onboarding draft and are saved back when valid;
 * - the preview follows the last valid inputs once they settle, keeping the
 *   last one on screen meanwhile, so an amount being retyped never blanks it;
 * - the projection is only run for a preview that matches what it was built from.
 */
export function useProposal(profile: RiskProfile, userId: number) {
    const draft = useOnboardingDraft()
    const [inputs, setInputs] = useState<ProposalInputs>(() => ({
        amount: draft.investmentAmount,
        monthly: draft.monthlyContribution,
        usesIsa: draft.usesIsa ?? profile.uses_isa,
        risk: clampLevel(draft.chosenRiskScore, profile.composite_score),
    }))
    const [target, setTarget] = useState(() => toRequest(inputs, userId))

    const change = (patch: Partial<ProposalInputs>) => {
        const next = { ...inputs, ...patch }
        setInputs(next)
        const nextRequest = toRequest(next, userId)
        if (nextRequest === null) return
        setTarget(nextRequest)
        draft.update({
            investmentAmount: nextRequest.investment_amount,
            monthlyContribution: nextRequest.monthly_contribution,
            usesIsa: nextRequest.uses_isa,
            chosenRiskScore: nextRequest.risk_score,
        })
    }

    const settled = useDebouncedValue(target, SETTLE_MS)
    const preview = usePreview(settled)
    const matches = preview.isSuccess && !preview.isPlaceholderData && settled !== null
    const projection = useMonteCarlo(matches ? projectionRequest(preview.data, settled, profile.time_horizon_years) : null)

    /** The inputs are not a valid proposal, so what is shown is the last one that was. */
    const invalid = toRequest(inputs, userId) === null
    /** True while what is shown is not yet what the valid inputs ask for. */
    const catchingUp = !invalid && (JSON.stringify(target) !== JSON.stringify(settled) || preview.isPlaceholderData || preview.isFetching)
    /** The preview on screen is exactly what the inputs ask for, so it can be opened. */
    const current = !invalid && matches && !catchingUp

    return { inputs, change, settled, preview, projection, current, catchingUp, invalid }
}
