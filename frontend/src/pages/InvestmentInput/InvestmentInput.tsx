import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAdvisorStore } from '../../store/useAdvisorStore'
import './InvestmentInput.css'

export default function InvestmentInput() {
    const navigate = useNavigate()
    const {
        investmentAmount, setInvestmentAmount,
        monthlyContribution, setMonthlyContribution,
        usesIsa, setUsesIsa,
        riskProfile,
    } = useAdvisorStore()

    const presets = [5000, 10000, 25000, 50000, 100000]
    const monthlyPresets = [0, 100, 250, 500, 1000]

    return (
        <motion.div
            className="invest page-container"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
        >
            <div className="page-header">
                <h1 className="page-title">How Much Will You Invest?</h1>
                <p className="page-subtitle">Set your initial investment and optional monthly contribution.</p>
            </div>

            <div className="invest__grid">
                {/* Lump Sum */}
                <div className="card invest__card">
                    <h3 className="card__title">Initial Investment</h3>
                    <p className="text-secondary" style={{ fontSize: 'var(--text-sm)', marginBottom: 'var(--space-4)' }}>
                        One-time lump sum deposit
                    </p>

                    <div className="invest__amount-display">
                        <span className="invest__currency">£</span>
                        <input
                            className="invest__amount-input font-mono"
                            type="number"
                            min={100}
                            value={investmentAmount}
                            onChange={e => setInvestmentAmount(Number(e.target.value))}
                        />
                    </div>

                    <div className="invest__presets">
                        {presets.map(p => (
                            <button
                                key={p}
                                className={`invest__preset font-mono ${investmentAmount === p ? 'invest__preset--active' : ''}`}
                                onClick={() => setInvestmentAmount(p)}
                            >
                                £{p.toLocaleString()}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Monthly */}
                <div className="card invest__card">
                    <h3 className="card__title">Monthly Contribution</h3>
                    <p className="text-secondary" style={{ fontSize: 'var(--text-sm)', marginBottom: 'var(--space-4)' }}>
                        Recurring monthly investment (optional)
                    </p>

                    <div className="invest__amount-display">
                        <span className="invest__currency">£</span>
                        <input
                            className="invest__amount-input font-mono"
                            type="number"
                            min={0}
                            value={monthlyContribution}
                            onChange={e => setMonthlyContribution(Number(e.target.value))}
                        />
                    </div>

                    <div className="invest__presets">
                        {monthlyPresets.map(p => (
                            <button
                                key={p}
                                className={`invest__preset font-mono ${monthlyContribution === p ? 'invest__preset--active' : ''}`}
                                onClick={() => setMonthlyContribution(p)}
                            >
                                {p === 0 ? 'None' : `£${p}`}
                            </button>
                        ))}
                    </div>
                </div>

                {/* ISA toggle */}
                <div className="card invest__card invest__isa-card">
                    <div className="invest__isa-row">
                        <div>
                            <h3 className="card__title">Stocks & Shares ISA</h3>
                            <p className="text-secondary" style={{ fontSize: 'var(--text-sm)' }}>
                                Tax-free wrapper (£20,000 annual limit). No CGT or dividend tax on gains.
                            </p>
                        </div>
                        <button
                            className={`invest__toggle ${usesIsa ? 'invest__toggle--on' : ''}`}
                            onClick={() => setUsesIsa(!usesIsa)}
                        >
                            <span className="invest__toggle-knob" />
                        </button>
                    </div>
                    {usesIsa && investmentAmount > 20000 && (
                        <div className="invest__isa-warning">
                            ⚠️ Your investment exceeds the £20,000 ISA annual limit.
                            The excess will be invested outside the ISA wrapper.
                        </div>
                    )}
                </div>
            </div>

            {/* Summary */}
            <div className="card invest__summary">
                <div className="invest__summary-grid">
                    <div className="stat">
                        <span className="stat__label">Initial</span>
                        <span className="stat__value font-mono">£{investmentAmount.toLocaleString()}</span>
                    </div>
                    <div className="stat">
                        <span className="stat__label">Monthly</span>
                        <span className="stat__value font-mono">£{monthlyContribution.toLocaleString()}</span>
                    </div>
                    <div className="stat">
                        <span className="stat__label">Year 1 Total</span>
                        <span className="stat__value font-mono">
                            £{(investmentAmount + monthlyContribution * 12).toLocaleString()}
                        </span>
                    </div>
                    <div className="stat">
                        <span className="stat__label">ISA</span>
                        <span className="stat__value">{usesIsa ? '✓ Active' : '—'}</span>
                    </div>
                </div>
            </div>

            <div className="asset-selection__cta">
                <button className="btn btn--ghost btn--lg" onClick={() => navigate('/assets')}>← Back</button>
                <button
                    className="btn btn--primary btn--lg"
                    disabled={investmentAmount < 100}
                    onClick={() => navigate('/builder')}
                >
                    Build Portfolio →
                </button>
            </div>
        </motion.div>
    )
}
