import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import './Landing.css'

export default function Landing() {
    const navigate = useNavigate()

    return (
        <motion.div
            className="landing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
        >
            <div className="landing__bg-grid" />

            <div className="landing__content">
                <motion.div
                    className="landing__badge"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                >
                    <span className="badge badge--blue">UK-FOCUSED • LSE ETFs • ZERO COST</span>
                </motion.div>

                <motion.h1
                    className="landing__title"
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                >
                    Algorithmic
                    <br />
                    <span className="landing__title-accent">Portfolio Engine</span>
                </motion.h1>

                <motion.p
                    className="landing__subtitle"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5 }}
                >
                    Mean-Variance Optimisation with Black-Litterman expected returns.
                    Built for UK retail investors using London Stock Exchange ETFs.
                </motion.p>

                <motion.div
                    className="landing__stats"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.7 }}
                >
                    <div className="landing__stat">
                        <span className="landing__stat-value font-mono">20+</span>
                        <span className="landing__stat-label">UK-Listed ETFs</span>
                    </div>
                    <div className="landing__stat-divider" />
                    <div className="landing__stat">
                        <span className="landing__stat-value font-mono">12</span>
                        <span className="landing__stat-label">Asset Classes</span>
                    </div>
                    <div className="landing__stat-divider" />
                    <div className="landing__stat">
                        <span className="landing__stat-value font-mono">£0</span>
                        <span className="landing__stat-label">Platform Fee</span>
                    </div>
                </motion.div>

                <motion.div
                    className="landing__cta"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.9 }}
                >
                    <button
                        className="btn btn--primary btn--lg landing__btn"
                        onClick={() => navigate('/onboarding')}
                    >
                        Start Risk Assessment
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                            <path d="M4 10h12m0 0l-4-4m4 4l-4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </button>
                    <button
                        className="btn btn--secondary btn--lg"
                        onClick={() => navigate('/dashboard')}
                    >
                        View Dashboard
                    </button>
                </motion.div>

                <motion.div
                    className="landing__features"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 1.1 }}
                >
                    {[
                        { icon: '◆', title: 'Black-Litterman', desc: 'Bayesian expected returns' },
                        { icon: '◆', title: 'Ledoit-Wolf', desc: 'Shrinkage covariance' },
                        { icon: '◆', title: 'Monte Carlo', desc: '30-year projections' },
                        { icon: '◆', title: 'Auto-Rebalance', desc: 'Threshold-based drift' },
                    ].map((f, i) => (
                        <div key={i} className="landing__feature">
                            <span className="landing__feature-icon">{f.icon}</span>
                            <div>
                                <div className="landing__feature-title">{f.title}</div>
                                <div className="landing__feature-desc">{f.desc}</div>
                            </div>
                        </div>
                    ))}
                </motion.div>
            </div>
        </motion.div>
    )
}
