import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAdvisorStore } from '../../store/useAdvisorStore'
import './Review.css'

export default function Review() {
    const navigate = useNavigate()
    const {
        riskProfile, portfolioResult, investmentAmount,
        monthlyContribution, usesIsa, userName,
    } = useAdvisorStore()

    if (!portfolioResult) {
        return (
            <div className="page-container" style={{ textAlign: 'center', paddingTop: 'var(--space-20)' }}>
                <h2>No portfolio to review</h2>
                <p className="text-secondary">Please complete the portfolio builder first.</p>
                <button className="btn btn--primary btn--lg" style={{ marginTop: 'var(--space-6)' }}
                    onClick={() => navigate('/builder')}>
                    Go to Builder
                </button>
            </div>
        )
    }

    const annualContribution = monthlyContribution * 12
    const year5Value = investmentAmount * Math.pow(1 + portfolioResult.expected_annual_return, 5)
        + (annualContribution > 0 ? annualContribution * ((Math.pow(1 + portfolioResult.expected_annual_return, 5) - 1) / portfolioResult.expected_annual_return) : 0)

    return (
        <motion.div
            className="review page-container"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
        >
            <div className="page-header">
                <h1 className="page-title">Review Your Portfolio</h1>
                <p className="page-subtitle">
                    {userName ? `${userName}, here` : 'Here'}'s a summary of your optimised portfolio.
                </p>
            </div>

            {/* Profile Summary */}
            <div className="review__grid">
                <div className="card review__section">
                    <h3 className="card__title">Risk Profile</h3>
                    <div className="review__detail-grid">
                        <div className="stat">
                            <span className="stat__label">Risk Score</span>
                            <span className="stat__value font-mono">{portfolioResult.risk_score.toFixed(0)}/10</span>
                        </div>
                        <div className="stat">
                            <span className="stat__label">Band</span>
                            <span className="stat__value" style={{ fontSize: 'var(--text-lg)' }}>{portfolioResult.risk_band}</span>
                        </div>
                        <div className="stat">
                            <span className="stat__label">Horizon</span>
                            <span className="stat__value font-mono">{riskProfile?.time_horizon_years || 10} yrs</span>
                        </div>
                        <div className="stat">
                            <span className="stat__label">ISA</span>
                            <span className="stat__value">{usesIsa ? '✓ Active' : '—'}</span>
                        </div>
                    </div>
                </div>

                <div className="card review__section">
                    <h3 className="card__title">Expected Performance</h3>
                    <div className="review__detail-grid">
                        <div className="stat">
                            <span className="stat__label">Annual Return</span>
                            <span className="stat__value text-positive font-mono">{(portfolioResult.expected_annual_return * 100).toFixed(2)}%</span>
                        </div>
                        <div className="stat">
                            <span className="stat__label">Volatility</span>
                            <span className="stat__value text-accent font-mono">{(portfolioResult.expected_volatility * 100).toFixed(2)}%</span>
                        </div>
                        <div className="stat">
                            <span className="stat__label">Sharpe Ratio</span>
                            <span className="stat__value font-mono">{portfolioResult.sharpe_ratio.toFixed(2)}</span>
                        </div>
                        <div className="stat">
                            <span className="stat__label">Total Fees</span>
                            <span className="stat__value font-mono">{(portfolioResult.total_expense_ratio * 100).toFixed(3)}%</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Investment Summary */}
            <div className="card review__section">
                <h3 className="card__title">Investment Summary</h3>
                <div className="review__summary-bar">
                    <div className="review__summary-item">
                        <span className="stat__label">Initial</span>
                        <span className="stat__value font-mono">£{investmentAmount.toLocaleString()}</span>
                    </div>
                    <div className="review__summary-divider" />
                    <div className="review__summary-item">
                        <span className="stat__label">Monthly</span>
                        <span className="stat__value font-mono">£{monthlyContribution.toLocaleString()}</span>
                    </div>
                    <div className="review__summary-divider" />
                    <div className="review__summary-item">
                        <span className="stat__label">Year 1 Total</span>
                        <span className="stat__value font-mono">£{(investmentAmount + annualContribution).toLocaleString()}</span>
                    </div>
                    <div className="review__summary-divider" />
                    <div className="review__summary-item">
                        <span className="stat__label">Projected (5yr)</span>
                        <span className="stat__value text-positive font-mono">
                            £{Math.round(year5Value).toLocaleString()}
                        </span>
                    </div>
                </div>
            </div>

            {/* Holdings Table */}
            <div className="card review__section">
                <h3 className="card__title">Portfolio Holdings</h3>
                <div className="review__table">
                    <div className="review__table-header">
                        <span>Asset Class</span>
                        <span>ETF</span>
                        <span>Weight</span>
                        <span>Amount</span>
                        <span>TER</span>
                    </div>
                    {portfolioResult.allocations.map((a, i) => (
                        <div key={i} className="review__table-row">
                            <span className="review__ac-name">{a.asset_class.replace(/_/g, ' ')}</span>
                            <span className="font-mono review__ticker">{a.ticker}</span>
                            <span className="font-mono">{(a.weight * 100).toFixed(1)}%</span>
                            <span className="font-mono">£{a.amount_gbp.toLocaleString()}</span>
                            <span className="font-mono text-muted">{(a.expense_ratio * 100).toFixed(2)}%</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* CTA */}
            <div className="review__cta">
                <button className="btn btn--ghost btn--lg" onClick={() => navigate('/builder')}>
                    ← Adjust Portfolio
                </button>
                <button
                    className="btn btn--primary btn--lg review__confirm-btn"
                    onClick={() => navigate('/dashboard')}
                >
                    Confirm & Go to Dashboard →
                </button>
            </div>
        </motion.div>
    )
}
