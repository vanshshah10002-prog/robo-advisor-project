import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { fetchUserPortfolios } from '../../api/client'
import { useAdvisorStore } from '../../store/useAdvisorStore'
import './PortfolioHistory.css'

export default function PortfolioHistory() {
    const navigate = useNavigate()
    const store = useAdvisorStore()
    const [portfolios, setPortfolios] = useState<any[]>([])
    const [isLoading, setIsLoading] = useState(true)

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

    const handleSelect = (p: any) => {
        // Mock loading the full portfolio result into the store
        // In a real app, we'd fetch the full details first
        store.setPortfolioResult(p) 
        navigate('/builder')
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
                                <span className="history__date text-muted">{new Date(p.created_at).toLocaleDateString()}</span>
                            </div>
                            <h3 className="history__card-name">{p.name || `Portfolio #${p.portfolio_id}`}</h3>
                            <div className="history__card-stats">
                                <div className="history__stat">
                                    <span className="stat__label">Amount</span>
                                    <span className="stat__value">£{p.investment_amount.toLocaleString()}</span>
                                </div>
                                <div className="history__stat">
                                    <span className="stat__label">Exp. Return</span>
                                    <span className="stat__value text-positive">{(p.expected_return * 100).toFixed(1)}%</span>
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
