import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { useAdvisorStore } from '../../store/useAdvisorStore'
import { CATEGORICAL, CHART_INK, allocationColours } from '../../lib/palette'
import './Dashboard.css'


function generateProjectionData(initial: number, monthly: number, annualReturn: number, years: number = 10) {
    const data = []
    let value = initial
    const monthlyReturn = annualReturn / 12
    for (let y = 0; y <= years; y++) {
        data.push({
            year: `Year ${y}`,
            value: Math.round(value),
            invested: initial + monthly * 12 * y,
        })
        for (let m = 0; m < 12; m++) {
            value = value * (1 + monthlyReturn) + monthly
        }
    }
    return data
}

export default function Dashboard() {
    const navigate = useNavigate()
    const { portfolioResult, investmentAmount, monthlyContribution, userName, resetAll } = useAdvisorStore()

    if (!portfolioResult) {
        return (
            <motion.div
                className="dashboard page-container"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
            >
                <div className="dashboard__empty">
                    <h2>No Portfolio Yet</h2>
                    <p className="text-secondary">Complete the advisory process to see your dashboard.</p>
                    <button className="btn btn--primary btn--lg" style={{ marginTop: 'var(--space-6)' }}
                        onClick={() => navigate('/onboarding')}>
                        Start Risk Assessment →
                    </button>
                </div>
            </motion.div>
        )
    }

    const projectionData = generateProjectionData(
        investmentAmount,
        monthlyContribution,
        portfolioResult.expected_annual_return,
        10,
    )

    const allocations = [...portfolioResult.allocations].sort((a, b) => b.weight - a.weight)
    const sliceColours = allocationColours(allocations.map(a => a.asset_class))
    const donutData = allocations.map(a => ({
        name: a.asset_class.replace(/_/g, ' '),
        value: Math.round(a.weight * 100 * 10) / 10,
        ticker: a.ticker,
        amount: a.amount_gbp,
    }))

    const projectedTotal = projectionData[projectionData.length - 1]?.value || 0
    const totalInvested = projectionData[projectionData.length - 1]?.invested || 0
    const projectedGain = projectedTotal - totalInvested

    return (
        <motion.div
            className="dashboard page-container"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
        >
            {/* Header */}
            <div className="dashboard__header">
                <div>
                    <h1 className="page-title">{userName ? `${userName}'s Portfolio` : 'Portfolio Dashboard'}</h1>
                    <p className="page-subtitle">
                        <span className="badge badge--blue">{portfolioResult.risk_band}</span>
                        {' '}Risk Score: <span className="font-mono">{portfolioResult.risk_score.toFixed(0)}/10</span>
                    </p>
                </div>
                <div className="dashboard__actions">
                    <button className="btn btn--secondary" onClick={() => navigate('/builder')}>
                        Adjust Portfolio
                    </button>
                    <button className="btn btn--ghost" onClick={() => { resetAll(); navigate('/') }}>
                        Start Over
                    </button>
                </div>
            </div>

            {/* Top Metrics */}
            <div className="dashboard__metrics grid-4">
                <motion.div className="card dashboard__metric"
                    initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
                    <span className="stat__label">Portfolio Value</span>
                    <span className="card__value font-mono">£{investmentAmount.toLocaleString()}</span>
                </motion.div>
                <motion.div className="card dashboard__metric"
                    initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
                    <span className="stat__label">Expected Return</span>
                    <span className="card__value text-positive font-mono">
                        {(portfolioResult.expected_annual_return * 100).toFixed(2)}%
                    </span>
                </motion.div>
                <motion.div className="card dashboard__metric"
                    initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
                    <span className="stat__label">Sharpe Ratio</span>
                    <span className="card__value font-mono">{portfolioResult.sharpe_ratio.toFixed(2)}</span>
                </motion.div>
                <motion.div className="card dashboard__metric"
                    initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
                    <span className="stat__label">10yr Projected</span>
                    <span className="card__value text-positive font-mono">
                        £{projectedTotal.toLocaleString()}
                    </span>
                    <span className="stat__change text-positive font-mono">
                        +£{projectedGain.toLocaleString()}
                    </span>
                </motion.div>
            </div>

            {/* Charts Row */}
            <div className="dashboard__charts grid-2">
                {/* Projection Chart */}
                <motion.div className="card"
                    initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}>
                    <h3 className="card__title">10-Year Projection</h3>
                    <div className="dashboard__chart-container">
                        <ResponsiveContainer width="100%" height={280}>
                            <AreaChart data={projectionData}>
                                <defs>
                                    <linearGradient id="projGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor={CATEGORICAL[0]} stopOpacity={0.3} />
                                        <stop offset="95%" stopColor={CATEGORICAL[0]} stopOpacity={0} />
                                    </linearGradient>
                                    <linearGradient id="investGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor={CHART_INK.axis} stopOpacity={0.2} />
                                        <stop offset="95%" stopColor={CHART_INK.axis} stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                                <XAxis dataKey="year" stroke="var(--text-muted)" fontSize={11} />
                                <YAxis
                                    stroke="var(--text-muted)"
                                    fontSize={11}
                                    tickFormatter={v => `£${(v / 1000).toFixed(0)}k`}
                                />
                                <Tooltip
                                    contentStyle={{
                                        background: 'var(--bg-elevated)',
                                        border: '1px solid var(--border)',
                                        borderRadius: '8px',
                                        fontSize: '13px',
                                    }}
                                    formatter={(value: number) => [`£${value.toLocaleString()}`, '']}
                                />
                                <Area type="monotone" dataKey="invested" stroke={CHART_INK.axis} fill="url(#investGrad)" name="Invested" />
                                <Area type="monotone" dataKey="value" stroke={CATEGORICAL[0]} fill="url(#projGrad)" strokeWidth={2} name="Projected" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </motion.div>

                {/* Allocation Donut */}
                <motion.div className="card"
                    initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }}>
                    <h3 className="card__title">Current Allocation</h3>
                    <div className="dashboard__chart-container">
                        <ResponsiveContainer width="100%" height={280}>
                            <PieChart>
                                <Pie
                                    data={donutData} cx="50%" cy="50%"
                                    innerRadius={70} outerRadius={100}
                                    dataKey="value" nameKey="name"
                                    startAngle={90} endAngle={-270}
                                    stroke="var(--bg-card)" strokeWidth={2}
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
                                            <div style={{
                                                background: 'var(--bg-elevated)',
                                                border: '1px solid var(--border)',
                                                borderRadius: '8px',
                                                padding: '8px 12px',
                                                fontSize: '13px',
                                            }}>
                                                <div style={{ fontWeight: 600, textTransform: 'capitalize' }}>{d.name}</div>
                                                <div className="font-mono">{d.value}% · £{d.amount?.toLocaleString()}</div>
                                            </div>
                                        )
                                    }}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                    <div className="dashboard__legend">
                        {donutData.map((d, i) => (
                            <div key={i} className="dashboard__legend-item">
                                <span className="dashboard__legend-dot" style={{ background: sliceColours[i] }} />
                                <span className="dashboard__legend-name">{d.name}</span>
                                <span className="dashboard__legend-val font-mono">{d.value}%</span>
                            </div>
                        ))}
                    </div>
                </motion.div>
            </div>

            {/* Holdings Table */}
            <motion.div className="card dashboard__holdings"
                initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.7 }}>
                <h3 className="card__title">Holdings</h3>
                <div className="dashboard__table">
                    <div className="dashboard__table-header">
                        <span>ETF</span>
                        <span>Asset Class</span>
                        <span>Weight</span>
                        <span>Value</span>
                        <span>TER</span>
                    </div>
                    {portfolioResult.allocations.map((a, i) => (
                        <div key={i} className="dashboard__table-row">
                            <div className="dashboard__etf-cell">
                                <span className="dashboard__etf-ticker font-mono">{a.ticker}</span>
                                <span className="dashboard__etf-name text-muted">{a.etf_name}</span>
                            </div>
                            <span style={{ textTransform: 'capitalize' }}>{a.asset_class.replace(/_/g, ' ')}</span>
                            <span className="font-mono">{(a.weight * 100).toFixed(1)}%</span>
                            <span className="font-mono">£{a.amount_gbp.toLocaleString()}</span>
                            <span className="font-mono text-muted">{(a.expense_ratio * 100).toFixed(2)}%</span>
                        </div>
                    ))}
                </div>
            </motion.div>
        </motion.div>
    )
}
