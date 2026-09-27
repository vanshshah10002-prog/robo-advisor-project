/**
 * Glossary
 * ========
 * The financial terms the app uses, each with the short explanation shown
 * when a reader hovers over it, taps it or tabs to it (see `ui/Term`). Kept
 * in one place so a term means the same thing wherever it appears.
 */
export const GLOSSARY = {
    real:
        'Future amounts are reduced by expected inflation, so each one shows what the money would buy at today’s prices. ' +
        'Use this to judge what a sum would really be worth to you.',
    nominal:
        'The number of pounds the account would actually show at the time, before allowing for rising prices. ' +
        'The figures are larger, but each pound would buy less than it does today.',
    median:
        'The middle of the simulated results: a 50% probability of ending above it and 50% below. ' +
        'It is a midpoint, not a prediction of the single most likely value.',
    range80:
        'In 80% of the simulations the value ends inside this range: a 10% probability of ending below it and 10% above it ' +
        '(the 10th to 90th percentile).',
    range50:
        'Half of the simulations end inside this range: a 25% probability of ending below it and 25% above it ' +
        '(the 25th to 75th percentile).',
    lossProbability:
        'The share of the simulations in which the portfolio ends worth less than the total paid in, ' +
        'on the same inflation basis as the other figures.',
    goalProbability: 'The share of the simulations in which the portfolio reaches the goal by the end of the period.',
    expectedReturn:
        'The estimated average return a year, after fund charges and before inflation, from the estimates made when the ' +
        'portfolio was built. Individual years will vary around it.',
    volatility:
        'The standard deviation of yearly returns: how widely they are expected to vary around the expected return. ' +
        'In about two years out of three, the return lands within one volatility of it.',
    sharpe:
        'Expected return above the risk-free rate, divided by volatility: the extra return expected for each unit of risk taken. ' +
        'Higher means more return for the risk.',
    riskFree: 'The return on cash with no risk of loss, as used when the portfolio was built. The Sharpe ratio is measured against it.',
    valueAtRisk:
        'A one-year loss that the estimates suggest would be exceeded in only 1 year in 20, assuming returns follow a normal ' +
        'distribution. Markets have fatter tails than that, so larger losses remain possible.',
    diversificationRatio:
        'The funds’ volatilities averaged by weight, divided by the portfolio’s volatility. Above 1 means the funds partly offset ' +
        'each other; the higher it is, the more the mix reduces risk.',
    effectiveHoldings:
        'How many equally sized holdings would be as concentrated as this portfolio (1 divided by the sum of the squared weights). ' +
        'A few large positions pull it well below the number of funds held.',
    ongoingCharges:
        'The funds’ yearly charges averaged by weight: the share of the portfolio’s value taken in fees each year, ' +
        'already allowed for in the expected return.',
    timeWeightedReturn:
        'Growth of the investments alone, removing the effect of when money was added or taken out. ' +
        'It is the standard way to compare one portfolio’s performance with another’s.',
    annualisedReturn: 'The time-weighted return expressed as a steady rate a year. Shown once there is a year of history.',
    realisedVolatility:
        'How much the portfolio’s value has actually moved, measured from its recorded daily values and scaled to a yearly figure. ' +
        'Shown once there are 21 days of values, which give 20 daily changes.',
    maxDrawdown: 'The largest fall from a previous high to a later low, as a share of that high.',
    riskContribution:
        'The share of the portfolio’s total risk that comes from this holding, allowing for how it moves with the others. ' +
        'It can be larger or smaller than its share of the money.',
    contributionToReturn:
        'This holding’s gain or loss as a share of all the money paid in. Across all holdings, the contributions add up to the ' +
        'portfolio’s return.',
    returnOnCost: 'The holding’s gain or loss as a share of what its units cost, trading costs included.',
    percentagePoints: 'Percentage points: the plain difference between two percentages. From 20% to 25% is 5 percentage points.',
    backtest:
        'The same construction rules run on past prices, deciding each date only with the data available on that date. ' +
        'A simulation, not this portfolio’s own history.',
} as const

export type GlossaryTerm = keyof typeof GLOSSARY
