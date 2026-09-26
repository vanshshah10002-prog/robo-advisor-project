/**
 * Minimal, schema-valid API payloads for tests. Each one parses against its
 * zod schema (asserted in api/endpoints.test.tsx), so a schema change that
 * breaks them fails fast.
 */

export const riskProfile = {
    user_id: 4,
    subjective_score: 5.2,
    objective_score: 4.8,
    composite_score: 5,
    risk_band: 'Balanced',
    risk_score_int: 5,
    time_horizon_years: 15,
    uses_isa: true,
    description: 'Balanced.',
}

export const quizQuestion = { id: 1, text: 'If your portfolio dropped 20%…', options: ['Sell', 'Hold', 'Buy'] }
export const minimalQuizQuestion = { ...quizQuestion, key: 'loss_reaction' }

export const createdPortfolio = {
    portfolio_id: 19,
    risk_score: 5,
    risk_band: 'Balanced',
    allocations: [
        { asset_class: 'global_equity', weight: 0.5, ticker: 'VWRL.L', etf_name: 'Vanguard FTSE All-World', expense_ratio: 0.0022, amount_gbp: 50_000 },
        { asset_class: 'global_bonds', weight: 0.5, ticker: 'VAGP.L', etf_name: 'Vanguard Global Aggregate Bond', expense_ratio: 0.001, amount_gbp: 50_000 },
    ],
    expected_annual_return: 0.044,
    expected_volatility: 0.078,
    sharpe_ratio: 0.31,
    total_expense_ratio: 0.0016,
    investment_amount: 100_000,
    tangent_portfolio: null,
    total_return_pct: 0,
}

export const portfolioDetail = {
    portfolio_id: 19,
    risk_score: 5,
    target_allocations: { global_equity: 0.5, global_bonds: 0.5 },
    selected_asset_classes: ['global_equity', 'global_bonds'],
    investment_amount: 100_000,
    monthly_contribution: 250,
    uses_isa: true,
    expected_return: 0.044,
    expected_volatility: null,
    sharpe_ratio: null,
    cash: 12.5,
    net_contributions: 100_000,
    total_return_pct: 0.245,
    last_valued_at: null,
    holdings: [
        { ticker: 'VWRL.L', asset_class: 'global_equity', units: 400, average_cost: 100, current_price: null, price_as_of: null, target_weight: 0.5, current_weight: null },
    ],
}

export const portfolioSummary = {
    portfolio_id: 19,
    name: null,
    risk_score: 5,
    investment_amount: 100_000,
    expected_return: null,
    created_at: '2026-09-01T10:00:00',
}

export const refreshResult = {
    portfolio_id: 19,
    total_value: 124_518,
    invested_value: 124_505.5,
    cash: 12.5,
    net_contributions: 100_000,
    total_return_pct: 0.245,
    stale_tickers: [],
    unpriced_tickers: [],
    valued_at: '2026-09-25T16:35:00',
    status: 'refreshed',
}

export const performance = {
    portfolio_id: 19,
    investment_amount: 100_000,
    net_contributions: 100_000,
    total_value: 124_518,
    cash: 12.5,
    total_return_pct: 0.245,
    valued_at: '2026-09-25T16:35:00',
    expected_return: 0.044,
    expected_volatility: 0.078,
    sharpe_ratio: 0.31,
    holdings: [
        { ticker: 'VWRL.L', asset_class: 'global_equity', units: 400, average_cost: 100, current_price: 155.6, current_value: 62_240, unrealised_pnl: 22_240, target_weight: 0.5, current_weight: 0.4998, band: 0.05 },
    ],
    drift: { 'VWRL.L': -0.0002 },
    portfolio_drift: 0.0004,
    needs_rebalance: false,
    rebalance_reasons: [],
    max_drift: 0.0002,
    target_allocations: { global_equity: 0.5 },
    unpriced_tickers: [],
}

export const rebalancePlan = {
    needs_rebalance: true,
    max_drift: 0.061,
    portfolio_drift: 0.03,
    reasons: ['growth sleeve outside its band'],
    out_of_band: ['VWRL.L'],
    trades: [
        { ticker: 'VWRL.L', etf_name: 'Vanguard FTSE All-World', action: 'sell', current_weight: 0.561, target_weight: 0.5, trade_value_gbp: 7_600, quantity: 48.8, price_gbp: 155.6, est_cost_gbp: 7.6, est_realised_gain_gbp: 2_720 },
    ],
    before_allocations: { 'VWRL.L': 0.561 },
    after_allocations: { 'VWRL.L': 0.5 },
    total_value_gbp: 124_518,
    est_total_cost_gbp: 15.2,
    est_realised_gain_gbp: 2_720,
    cgt_applies: false,
    stale_tickers: [],
    executed: false,
}

export const contributionResult = {
    portfolio_id: 19,
    deposited_gbp: 500,
    buys: [{ ticker: 'VAGP.L', value_gbp: 500, units: 21.4 }],
    total_value: 125_018,
    portfolio_drift: 0.001,
    needs_rebalance: false,
}

export const transaction = {
    id: 1,
    ticker: 'VWRL.L',
    action: 'buy',
    quantity: 400,
    price: 100,
    value: 40_000,
    cost: 40,
    realised_gain: 0,
    timestamp: '2021-09-27T16:35:00',
    notes: null,
}

export const monteCarlo = {
    percentile_10: [100_000, 98_000],
    percentile_25: [100_000, 103_000],
    percentile_50: [100_000, 108_000],
    percentile_75: [100_000, 113_000],
    percentile_90: [100_000, 119_000],
    years: [0, 1],
    probability_of_goal: null,
    expected_final_value: 108_400,
    median_final_value: 108_000,
}

export const efficientFrontier = {
    frontier_points: [{ expected_return: 0.05, volatility: 0.1, sharpe_ratio: 0.3, weights: { global_equity: 0.6, global_bonds: 0.4 } }],
    current_portfolio: null,
    risk_free_rate: 0.04,
}

export const etf = {
    ticker: 'VWRL.L',
    name: 'Vanguard FTSE All-World UCITS ETF (GBP)',
    asset_class: 'global_equity',
    expense_ratio: 0.0022,
    currency: 'GBP',
}

export const assetClass = {
    id: 'global_equity',
    name: 'Global Equity',
    description: 'Developed and emerging markets',
    risk_level: 4,
    primary_etf: 'VWRL.L',
    primary_etf_name: 'Vanguard FTSE All-World',
    expense_ratio: 0.0022,
    factsheet_url: null,
    etf_count: 3,
}

export const priceBar = { date: '2026-09-25', open: 155, high: 156, low: 154.5, close: 155.6, volume: 120_000 }
export const latestPrice = { ticker: 'VWRL.L', price_gbp: 155.6, price: 155.6, as_of: '2026-09-25' }
