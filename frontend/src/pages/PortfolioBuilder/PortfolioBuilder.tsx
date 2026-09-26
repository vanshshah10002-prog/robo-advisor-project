import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import { useAdvisorStore, type PortfolioResult } from '../../store/useAdvisorStore'
import { createPortfolio, refreshPortfolio } from '../../api/client'
import { allocationColours } from '../../lib/palette'
import './PortfolioBuilder.css'


export default function PortfolioBuilder() {
    const navigate = useNavigate()
    const store = useAdvisorStore()
    const [isOptimising, setIsOptimising] = useState(false)
    const [isRefreshing, setIsRefreshing] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [localRisk, setLocalRisk] = useState(store.adjustedRiskScore || store.riskProfile?.risk_score_int || 5)

    const riskBands: Record<number, string> = {
        1: "Capital Preservation", 2: "Very Conservative", 3: "Conservative",
        4: "Moderately Conservative", 5: "Balanced", 6: "Moderately Aggressive",
        7: "Growth", 8: "Aggressive Growth", 9: "High Risk", 10: "Maximum Growth",
    }

    const handleOptimise = async () => {
        setIsOptimising(true)
        setError(null)
        try {
            const result = await createPortfolio({
                user_id: store.riskProfile?.user_id || 1,
                risk_score: localRisk,
                investment_amount: store.investmentAmount,
                monthly_contribution: store.monthlyContribution,
                uses_isa: store.usesIsa,
            }) as PortfolioResult

            store.setAdjustedRiskScore(localRisk)
            store.setPortfolioResult(result)
        } catch (e) {
            setError(e instanceof Error && e.message ? e.message : 'Optimisation failed.')
        } finally {
            setIsOptimising(false)
        }
    }

    const handleRefresh = async () => {
        if (!portfolio?.portfolio_id) return
        setIsRefreshing(true)
        try {
            const res = await refreshPortfolio(portfolio.portfolio_id)
            store.setPortfolioResult({
                ...portfolio,
                total_return_pct: res.total_return_pct
            })
        } catch (e) {
            console.error("Refresh failed", e)
        } finally {
            setIsRefreshing(false)
        }
    }

    useEffect(() => {
        handleOptimise()
    }, [])

    const portfolio = store.portfolioResult
    const allocations = [...(portfolio?.allocations ?? [])].sort((a, b) => b.weight - a.weight)
    const sliceColours = allocationColours(allocations.map(a => a.asset_class))
    const donutData = allocations.map(a => ({
        name: a.asset_class.replace(/_/g, ' '),
        value: Math.round(a.weight * 10000) / 100,
        ticker: a.ticker,
        amount: a.amount_gbp,
    }))

    return (
        <motion.div
            className="builder page-container"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
        >
            <div className="page-header builder__header">
                <div>
                    <h1 className="page-title">Portfolio Strategy</h1>
                    <p className="page-subtitle">
                        Algorithmic MVO allocation for {store.riskProfile?.name || 'Advisor User'}.
                    </p>
                </div>
                <div className="builder__header-actions">
                    <button className="btn btn--secondary" onClick={() => navigate('/history')}>View Vault</button>
                    <button className="btn btn--primary" onClick={handleRefresh} disabled={isRefreshing || !portfolio}>
                        {isRefreshing ? 'Syncing...' : 'Refresh Prices'}
                    </button>
                </div>
            </div>

            {/* Summary Analytics Dashboard */}
            {portfolio && (
                <div className="builder__summary-grid">
                    <motion.div className="card summary-card" whileHover={{ y: -5 }}>
                        <span className="summary-card__label">Portfolio Return</span>
                        <span className={`summary-card__value ${(portfolio.total_return_pct || 0) >= 0 ? 'text-positive' : 'text-negative'}`}>
                            {((portfolio.total_return_pct || 0) * 100).toFixed(2)}%
                        </span>
                        <span className="summary-card__sub">Since creation</span>
                    </motion.div>
                    <motion.div className="card summary-card" whileHover={{ y: -5 }}>
                        <span className="summary-card__label">Expected Alpha</span>
                        <span className="summary-card__value text-accent">
                            {( (portfolio.alpha || 0) * 100).toFixed(2)}%
                        </span>
                        <span className="summary-card__sub">Over risk-free rate</span>
                    </motion.div>
                    <motion.div className="card summary-card" whileHover={{ y: -5 }}>
                        <span className="summary-card__label">Sharpe Ratio</span>
                        <span className="summary-card__value">
                            {portfolio.sharpe_ratio.toFixed(2)}
                        </span>
                        <span className="summary-card__sub">Risk-adjusted metric</span>
                    </motion.div>
                    <motion.div className="card summary-card" whileHover={{ y: -5 }}>
                        <span className="summary-card__label">Risk Level</span>
                        <span className="summary-card__value text-secondary">
                            {localRisk}/10
                        </span>
                        <span className="summary-card__sub">{riskBands[localRisk]}</span>
                    </motion.div>
                </div>
            )}

            {/* Risk Slider */}
            <div className="card builder__risk-card">
                <div className="builder__risk-header">
                    <div>
                        <h3 className="card__title">Risk Level</h3>
                        <p className="text-secondary" style={{ fontSize: 'var(--text-sm)' }}>
                            {riskBands[localRisk]}
                        </p>
                    </div>
                    <div className="builder__risk-value font-mono">
                        {localRisk}<span className="text-muted">/10</span>
                    </div>
                </div>
                <div className="builder__slider-row">
                    <span className="builder__slider-label font-mono">Conservative</span>
                    <input
                        className="builder__slider"
                        type="range"
                        min={1}
                        max={10}
                        step={1}
                        value={localRisk}
                        onChange={e => setLocalRisk(Number(e.target.value))}
                        style={{ '--val': `${((localRisk - 1) / 9) * 100}%` } as React.CSSProperties}
                    />
                    <span className="builder__slider-label font-mono">Aggressive</span>
                </div>
                <button
                    className="btn btn--primary builder__optimise-btn"
                    onClick={handleOptimise}
                    disabled={isOptimising}
                >
                    {isOptimising ? 'Optimising...' : 'Re-Optimise Portfolio'}
                </button>
            </div>

            {error && (
                <div className="builder__error">
                    ⚠️ {error} — showing estimated allocation.
                </div>
            )}

            {portfolio && (
                <div className="builder__grid">
                    {/* Donut Chart */}
                    <div className="card builder__chart-card">
                        <h3 className="card__title">Target Allocation</h3>
                        <div className="builder__donut-container">
                            <ResponsiveContainer width="100%" height={300}>
                                <PieChart>
                                    <Pie
                                        data={donutData}
                                        cx="50%"
                                        cy="50%"
                                        innerRadius={80}
                                        outerRadius={120}
                                        dataKey="value"
                                        nameKey="name"
                                        startAngle={90}
                                        endAngle={-270}
                                        stroke="var(--bg-card)"
                                        strokeWidth={2}
                                    >
                                        {donutData.map((_, i) => (
                                            <Cell key={i} fill={sliceColours[i]} />
                                        ))}
                                    </Pie>
                                    <Tooltip
                                        content={({ payload }) => {
                                            if (!payload?.length) return null
                                            const d = payload[0].payload
                                            return (
                                                <div className="builder__tooltip">
                                                    <div className="builder__tooltip-name">{d.name}</div>
                                                    <div className="font-mono">{d.value.toFixed(1)}%</div>
                                                    <div className="font-mono text-muted">£{d.amount?.toLocaleString()}</div>
                                                </div>
                                            )
                                        }}
                                    />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>

                        {/* Legend */}
                        <div className="builder__legend">
                            {donutData.map((d, i) => (
                                <div key={i} className="builder__legend-item">
                                    <span
                                        className="builder__legend-dot"
                                        style={{ background: sliceColours[i] }}
                                    />
                                    <span className="builder__legend-name">{d.name}</span>
                                    <span className="builder__legend-pct font-mono">{d.value.toFixed(1)}%</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Performance Metrics */}
                    <div className="builder__metrics-col">
                        <div className="card builder__metric-card">
                            <span className="stat__label">Expected Annual Return</span>
                            <span className="card__value text-positive">
                                {(portfolio.expected_annual_return * 100).toFixed(2)}%
                            </span>
                        </div>
                        <div className="card builder__metric-card">
                            <span className="stat__label">Expected Volatility</span>
                            <span className="card__value text-accent">
                                {(portfolio.expected_volatility * 100).toFixed(2)}%
                            </span>
                        </div>
                        <div className="card builder__metric-card">
                            <span className="stat__label">Sharpe Ratio</span>
                            <span className="card__value">
                                {portfolio.sharpe_ratio.toFixed(2)}
                            </span>
                        </div>
                        <div className="card builder__metric-card">
                            <span className="stat__label">Total Expense Ratio</span>
                            <span className="card__value text-secondary">
                                {(portfolio.total_expense_ratio * 100).toFixed(3)}%
                            </span>
                        </div>

                        {/* ETF Breakdown */}
                        <div className="card">
                            <h3 className="card__title" style={{ marginBottom: 'var(--space-4)' }}>ETF Breakdown</h3>
                            {portfolio.allocations.map((a, i) => (
                                <div key={i} className="builder__etf-row">
                                    <div className="builder__etf-info">
                                        <span className="builder__etf-ticker font-mono">{a.ticker}</span>
                                        <span className="builder__etf-name text-secondary">{a.etf_name}</span>
                                    </div>
                                    <div className="builder__etf-stats">
                                        <span className="font-mono">{(a.weight * 100).toFixed(1)}%</span>
                                        <span className="font-mono text-muted">£{a.amount_gbp.toLocaleString()}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            <div className="asset-selection__cta">
                <button className="btn btn--ghost btn--lg" onClick={() => navigate('/invest')}>← Back</button>
                <button
                    className="btn btn--primary btn--lg"
                    onClick={() => navigate('/review')}
                    disabled={!portfolio}
                >
                    Review & Confirm →
                </button>
            </div>
        </motion.div>
    )
}
