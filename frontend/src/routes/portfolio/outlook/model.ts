/**
 * The outlook in words and requests. The projection starts from what the
 * portfolio is worth now and uses the expected return and volatility stored
 * when it was opened; the backend refuses rather than inventing either.
 */
import type { MonteCarlo, MonteCarloRequest, TrackRecord } from '@/api/schemas'
import { money, percent } from '@/lib/format'

export const OUTLOOK_PATHS = 2_000
export const MAX_YEARS = 50
/** The share of outcomes within one standard deviation of the mean, when the volatility estimate is right. */
const WELL_JUDGED = 0.68

export interface OutlookInputs {
    years: number | null
    monthly: number | null
    /** Adjusted for inflation when `realTerms`, otherwise in pounds as they would be at the time. */
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

const basis = (mc: MonteCarlo) => (mc.real_terms ? 'adjusted for inflation' : 'not adjusted for inflation')
const after = (years: number) => `${years} year${years === 1 ? '' : 's'}`

/** "In 15 years, adjusted for inflation, the median projection is £X, with an 80% probability of ending between £A and £B." */
export function outlookSentence(mc: MonteCarlo): string {
    const end = mc.years.length - 1
    return (
        `In ${after(mc.years[end])}, ${basis(mc)}, the median projection is ${money(mc.percentile_50[end])}, ` +
        `with an 80% probability of ending between ${money(mc.percentile_10[end])} and ${money(mc.percentile_90[end])}.`
    )
}

/** How the probability of ending below what was paid in changes, from the first year to the last. */
export function lossSentence(mc: MonteCarlo): string | null {
    const odds = mc.loss_probability_by_year
    if (odds.length < 2) return null
    const [first, last] = [odds[1], odds[odds.length - 1]]
    const years = mc.years[mc.years.length - 1]
    const change = last < first ? 'falls' : last > first ? 'rises' : 'stays'
    const ending = change === 'stays' ? `at ${percent(first, 0)} throughout` : `from ${percent(first, 0)} after 1 year to ${percent(last, 0)} after ${after(years)}`
    return `The probability of ending below the amount paid in ${change} ${ending}.`
}

/** How often the backtest's forecasts held, as a check on reading the fan too literally. */
export function accuracyNote(record: TrackRecord): string | null {
    if (record.within_one_sigma === null) return null
    return (
        `In the walk-forward backtest at risk level ${record.risk}, ${percent(record.within_one_sigma, 0)} of yearly returns landed within one ` +
        `standard deviation of the return forecast at the time; if the volatility estimates were accurate, about ${percent(WELL_JUDGED, 0)} would.`
    )
}

