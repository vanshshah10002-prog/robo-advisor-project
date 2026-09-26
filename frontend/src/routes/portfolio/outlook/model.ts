/**
 * The outlook in words and requests. The projection starts from what the
 * portfolio is worth now and uses the expected return and volatility stored
 * when it was opened; the backend refuses rather than inventing either.
 */
import type { MonteCarlo, MonteCarloRequest, TrackRecord } from '@/api/schemas'
import { money, percent } from '@/lib/format'

export const OUTLOOK_PATHS = 2_000
export const MAX_YEARS = 50
/** What a forecast whose swing was judged right would score: one standard deviation either side. */
const WELL_JUDGED = 0.68

export interface OutlookInputs {
    years: number | null
    monthly: number | null
    /** In today's money when `realTerms`, otherwise in the pounds of the day. */
    goal: number | null
    realTerms: boolean
}

export const validYears = (years: number | null): years is number =>
    years !== null && Number.isInteger(years) && years >= 1 && years <= MAX_YEARS

/** The simulation for these inputs, or null while one of them is not a usable figure. */
export function outlookRequest(portfolioId: number, value: number, inputs: OutlookInputs): MonteCarloRequest | null {
    const { years, monthly, goal, realTerms } = inputs
    if (!validYears(years) || monthly === null || monthly < 0 || value <= 0 || (goal !== null && goal <= 0)) return null
    return {
        portfolio_id: portfolioId,
        initial_investment: value,
        monthly_contribution: monthly,
        years,
        n_simulations: OUTLOOK_PATHS,
        real_terms: realTerms,
        ...(goal === null ? {} : { goal_amount: goal }),
    }
}

const basis = (mc: MonteCarlo) => (mc.real_terms ? "in today's money" : 'in the pounds of the day')
const after = (years: number) => `${years} year${years === 1 ? '' : 's'}`

/** "In 15 years, in today's money, the middle outcome is £X; 8 in 10 simulated outcomes land between £A and £B." */
export function outlookSentence(mc: MonteCarlo): string {
    const end = mc.years.length - 1
    return (
        `In ${after(mc.years[end])}, ${basis(mc)}, the middle outcome is ${money(mc.percentile_50[end])}; ` +
        `8 in 10 simulated outcomes land between ${money(mc.percentile_10[end])} and ${money(mc.percentile_90[end])}.`
    )
}

/** How the chance of being below what was paid in changes, from the first year to the last. */
export function lossSentence(mc: MonteCarlo): string | null {
    const odds = mc.loss_probability_by_year
    if (odds.length < 2) return null
    const [first, last] = [odds[1], odds[odds.length - 1]]
    const years = mc.years[mc.years.length - 1]
    const change = last < first ? 'falls' : last > first ? 'rises' : 'stays'
    const ending = change === 'stays' ? `at ${percent(first, 0)} throughout` : `from ${percent(first, 0)} after a year to ${percent(last, 0)} after ${after(years)}`
    return `The chance of being worth less than was paid in ${change} ${ending}.`
}

/** How often the backtest's forecasts held, as a check on reading the fan too literally. */
export function accuracyNote(record: TrackRecord): string | null {
    if (record.within_one_sigma === null) return null
    return (
        `In the walk-forward test at level ${record.risk}, ${percent(record.within_one_sigma, 0)} of yearly returns landed within one ` +
        `typical swing of the forecast made at the time; a forecast whose swing was judged right would manage about ${percent(WELL_JUDGED, 0)}.`
    )
}

