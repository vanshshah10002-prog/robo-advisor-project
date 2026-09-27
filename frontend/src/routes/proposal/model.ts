/**
 * The proposal in words and requests. Pure, so the sentence a person reads
 * and the projection it rests on are both unit-tested.
 */
import type { MonteCarloRequest, Preview, PreviewRequest } from '@/api/schemas'
import { sleeveTotals } from '@/charts/model'
import { money, percent } from '@/lib/format'
import { level } from '@/lib/risk'

export const PROJECTION_PATHS = 2_000
const MAX_YEARS = 50

/**
 * The one-sentence summary at the top of the proposal, built only from the
 * preview's own figures: "£50,000 now and £250 a month, at level 6.3: …".
 */
export function proposalSentence(preview: Preview, amount: number, monthly: number): string {
    const { growth, defensive } = sleeveTotals(preview.allocations)
    const flows = monthly > 0 ? `${money(amount)} now and ${money(monthly)} a month` : `${money(amount)} now`
    const funds = preview.allocations.length
    return (
        `${flows}, at risk level ${level(preview.risk_score)}: ${percent(growth, 0)} in growth and ${percent(defensive, 0)} in defensive holdings, ` +
        `spread across ${funds} fund${funds === 1 ? '' : 's'} costing about ${money(preview.annual_fund_cost_gbp)} a year.`
    )
}

/**
 * The simulation behind the projection: the preview's expected return and
 * volatility, the amounts it was built for, over the investor's horizon,
 * adjusted for inflation.
 */
export function projectionRequest(preview: Preview, built: PreviewRequest, horizonYears: number): MonteCarloRequest {
    return {
        annual_return: preview.expected_annual_return,
        annual_volatility: preview.expected_volatility,
        initial_investment: built.investment_amount,
        monthly_contribution: built.monthly_contribution,
        years: Math.min(MAX_YEARS, Math.max(1, Math.round(horizonYears))),
        n_simulations: PROJECTION_PATHS,
        real_terms: true,
    }
}
