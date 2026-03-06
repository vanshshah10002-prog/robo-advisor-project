import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import { useAdvisorStore } from '../../store/useAdvisorStore'
import { fetchAssetClasses } from '../../api/client'
import type { AssetClassInfo } from '../../api/client'
import './AssetSelection.css'

const RISK_ICON: Record<number, string> = { 1: '🛡️', 2: '📊', 3: '⚖️', 4: '📈', 5: '🚀' }

export default function AssetSelection() {
    const navigate = useNavigate()
    const { selectedAssetClasses, toggleAssetClass, riskProfile } = useAdvisorStore()

    const { data: assetClasses, isLoading, error } = useQuery({
        queryKey: ['asset-classes'],
        queryFn: fetchAssetClasses,
    })

    const canContinue = selectedAssetClasses.length >= 3

    if (isLoading) {
        return (
            <div className="page-container" style={{ textAlign: 'center', paddingTop: 'var(--space-20)' }}>
                <h2>Loading Asset Classes...</h2>
                <p className="text-secondary">Fetching from the ETF registry.</p>
            </div>
        )
    }

    if (error || !assetClasses) {
        return (
            <div className="page-container" style={{ textAlign: 'center', paddingTop: 'var(--space-20)' }}>
                <h2>Could not load asset classes</h2>
                <p className="text-secondary">
                    Make sure the backend is running at http://127.0.0.1:8000
                </p>
                <button className="btn btn--primary btn--lg" style={{ marginTop: 'var(--space-6)' }}
                    onClick={() => window.location.reload()}>
                    Retry
                </button>
            </div>
        )
    }

    return (
        <motion.div
            className="asset-selection page-container"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
        >
            <div className="page-header">
                <h1 className="page-title">Choose Your Asset Classes</h1>
                <p className="page-subtitle">
                    Select at least 3 asset classes to build your diversified portfolio.
                    {' '}<span className="font-mono text-muted">{assetClasses.length} available</span>
                    {riskProfile && (
                        <span className="asset-selection__risk-tag">
                            {' '}· Risk Profile: <span className="badge badge--blue">{riskProfile.risk_band}</span>
                        </span>
                    )}
                </p>
            </div>

            <div className="asset-selection__grid">
                {assetClasses.map((ac: AssetClassInfo, i: number) => {
                    const isSelected = selectedAssetClasses.includes(ac.id)
                    return (
                        <motion.div
                            key={ac.id}
                            className={`card card--interactive ${isSelected ? 'card--selected' : ''}`}
                            onClick={() => toggleAssetClass(ac.id)}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.03 }}
                        >
                            <div className="asset-card__header">
                                <span className="asset-card__icon">{RISK_ICON[ac.risk_level] || '📊'}</span>
                                {isSelected && <span className="asset-card__check">✓</span>}
                            </div>
                            <h3 className="asset-card__name">{ac.name}</h3>
                            <p className="asset-card__desc">{ac.description}</p>
                            <div className="asset-card__footer">
                                <span className="asset-card__etf font-mono">{ac.primary_etf || '—'}</span>
                                {ac.expense_ratio != null && (
                                    <span className="asset-card__fee font-mono">
                                        {(ac.expense_ratio * 100).toFixed(2)}% TER
                                    </span>
                                )}
                            </div>
                            <div className="asset-card__meta-row">
                                <div className="asset-card__risk">
                                    {Array.from({ length: 5 }, (_, j) => (
                                        <div
                                            key={j}
                                            className={`asset-card__risk-dot ${j < ac.risk_level ? 'asset-card__risk-dot--active' : ''}`}
                                        />
                                    ))}
                                </div>
                                {ac.etf_count > 1 && (
                                    <span className="asset-card__alt-count font-mono">{ac.etf_count} ETFs</span>
                                )}
                            </div>
                            {ac.factsheet_url && (
                                <a
                                    className="asset-card__factsheet"
                                    href={ac.factsheet_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    onClick={e => e.stopPropagation()}
                                >
                                    📄 View ETF Factsheet
                                </a>
                            )}
                        </motion.div>
                    )
                })}
            </div>

            <div className="asset-selection__cta">
                <button className="btn btn--ghost btn--lg" onClick={() => navigate('/onboarding')}>
                    ← Back
                </button>
                <div className="asset-selection__count font-mono">
                    {selectedAssetClasses.length} selected
                    {selectedAssetClasses.length < 3 && (
                        <span className="text-muted"> (min 3)</span>
                    )}
                </div>
                <button
                    className="btn btn--primary btn--lg"
                    disabled={!canContinue}
                    onClick={() => navigate('/invest')}
                >
                    Continue →
                </button>
            </div>
        </motion.div>
    )
}
