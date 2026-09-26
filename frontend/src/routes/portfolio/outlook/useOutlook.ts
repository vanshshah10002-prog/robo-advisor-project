import { useState } from 'react'
import { useMonteCarlo, useRiskProfile } from '@/api/queries'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { useIdentity } from '@/store/session'
import { outlookRequest, type OutlookInputs } from './model'

/** Long enough for typed figures to settle before a new simulation. */
const SETTLE_MS = 450
/** The horizon when this browser has no risk profile to take one from. */
export const DEFAULT_YEARS = 10

/**
 * The outlook's inputs and its simulation. The horizon starts from this
 * browser's risk profile, the monthly amount from the portfolio's own, and
 * the projection from what the portfolio is worth now.
 */
export function useOutlook(portfolioId: number, value: number, monthly: number) {
    const userId = useIdentity((s) => s.userId)
    const profile = useRiskProfile(userId)
    const [edits, setEdits] = useState<Partial<OutlookInputs>>({})

    const inputs: OutlookInputs = {
        years: profile.data?.time_horizon_years ?? DEFAULT_YEARS,
        monthly,
        goal: null,
        realTerms: true,
        ...edits,
    }
    const change = (patch: Partial<OutlookInputs>) => setEdits((current) => ({ ...current, ...patch }))

    const request = outlookRequest(portfolioId, value, inputs)
    const settled = useDebouncedValue(request, SETTLE_MS)
    const projection = useMonteCarlo(settled)
    const catchingUp = request === null || JSON.stringify(request) !== JSON.stringify(settled) || projection.isPlaceholderData

    return { inputs, change, projection, invalid: request === null, catchingUp }
}
