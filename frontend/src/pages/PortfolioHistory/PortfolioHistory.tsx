import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { fetchUserPortfolios } from '../../api/client'
import { getPortfolio } from '../../api/endpoints'
import type { PortfolioSummary } from '../../api/schemas'
import { date, money, percent } from '../../lib/format'
import { useAdvisorStore } from '../../store/useAdvisorStore'
import './PortfolioHistory.css'

export default function PortfolioHistory() {
    const navigate = useNavigate()
    const store = useAdvisorStore()
    const [portfolios, setPortfolios] = useState<PortfolioSummary[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [selectError, setSelectError] = useState<string | null>(null)

    useEffect(() => {
        const loadPortfolios = async () => {
            try {
                // Defaulting to user_id = 1 for the demo
                const res = await fetchUserPortfolios(1)
                setPortfolios(res)
            } catch (e) {
                console.error("Failed to load portfolios", e)
            } finally {
                setIsLoading(false)
            }
        }
        loadPortfolios()
    }, [])

    // The summary row lacks allocations and metrics, so loading it as a full
    // result crashed the builder. Load the stored inputs and let the builder
    // rebuild from all of them. Replaced by the portfolio workspace in Phase 4.
    const handleSelect = async (p: PortfolioSummary) => {
        setSelectError(null)
        try {
            const detail = await getPortfolio(p.portfolio_id)
            store.setAdjustedRiskScore(Math.round(detail.risk_score))
            store.setInvestmentAmount(detail.investment_amount)
            store.setMonthlyContribution(detail.monthly_contribution)
            store.setUsesIsa(detail.uses_isa)
            navigate('/builder')
        } catch (e) {
            setSelectError(e instanceof Error ? e.message : 'Could not open that portfolio.')
        }
    }

    return (
        <motion.div 
            className="history page-container"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
        >
            <div className="page-header">
                <h1 className="page-title">Saved Portfolios</h1>
                <p className="page-subtitle">Select a previously created strategy to view its performance.</p>
            </div>

            {selectError && (
                <p className="text-negative" role="alert">{selectError}</p>
            )}

            {isLoading ? (
                <div className="history__loading">Loading your vault...</div>
            ) : portfolios.length === 0 ? (
                <div className="history__empty card">
                    <h3>No portfolios found</h3>
                    <p className="text-secondary">Start by creating your first automated investment strategy.</p>
                    <button className="btn btn--primary" onClick={() => navigate('/onboarding')}>Get Started</button>
                </div>
            ) : (
                <div className="history__grid">
                    {portfolios.map((p) => (
                        <motion.div 
                            key={p.portfolio_id}
                            className="card history__card clickable"
                            whileHover={{ y: -5, scale: 1.02 }}
                            onClick={() => handleSelect(p)}
                        >
                            <div className="history__card-header">
                                <span className="history__risk-badge font-mono">Risk {Math.round(p.risk_score)}</span>
                                <span className="history__date text-muted">{date(p.created_at)}</span>
                            </div>
                            <h3 className="history__card-name">{p.name || `Portfolio #${p.portfolio_id}`}</h3>
                            <div className="history__card-stats">
                                <div className="history__stat">
                                    <span className="stat__label">Amount</span>
                                    <span className="stat__value">{money(p.investment_amount)}</span>
                                </div>
                                <div className="history__stat">
                                    <span className="stat__label">Exp. Return</span>
                                    <span className="stat__value text-positive">{percent(p.expected_return)}</span>
                                </div>
                            </div>
                        </motion.div>
                    ))}
                    
                    <motion.div 
                        className="card history__card history__card--new clickable"
                        whileHover={{ scale: 1.02 }}
                        onClick={() => navigate('/onboarding')}
                    >
                        <div className="history__new-icon">+</div>
                        <h3>Create New</h3>
                    </motion.div>
                </div>
            )}

            <div className="history__actions">
                <button className="btn btn--ghost" onClick={() => navigate('/')}>← Home</button>
            </div>
        </motion.div>
    )
}
