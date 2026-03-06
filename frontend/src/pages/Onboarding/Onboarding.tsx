import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import { useAdvisorStore } from '../../store/useAdvisorStore'
import { fetchQuizQuestions, submitRiskProfile } from '../../api/client'
import type { QuizQuestion } from '../../api/client'
import './Onboarding.css'

const OBJECTIVE_STEP = 11
const RESULT_STEP = 12

export default function Onboarding() {
    const navigate = useNavigate()
    const [step, setStep] = useState(0) // 0 = name, 1-10 = quiz, 11 = objective, 12 = result
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [localName, setLocalName] = useState('')
    const [objectiveForm, setObjectiveForm] = useState({
        monthly_income: '',
        monthly_expenses: '',
        total_investable_assets: '',
        investment_amount: '10000',
        employment_type: 'employed',
        time_horizon_years: '10',
        has_emergency_fund: 'yes',
    })

    const store = useAdvisorStore()

    // Fallback questions if API unavailable
    const fallbackQuestions: QuizQuestion[] = [
        { id: 1, text: "If your portfolio dropped 20% in a month, what would you do?", options: ["Sell everything", "Sell some holdings", "Hold and wait", "Buy a little more", "Buy aggressively — it's on sale"] },
        { id: 2, text: "What is your primary investment goal?", options: ["Capital preservation", "Steady income", "Balanced growth", "Capital growth", "Maximum growth at any cost"] },
        { id: 3, text: "How long is your investment horizon?", options: ["Less than 1 year", "1–3 years", "3–5 years", "5–10 years", "10+ years"] },
        { id: 4, text: "What percentage of your net worth is this investment?", options: ["Less than 5%", "5–15%", "15–30%", "30–50%", "More than 50%"] },
        { id: 5, text: "How would you describe your investment knowledge?", options: ["None", "Basic", "Intermediate", "Advanced", "Expert / Professional"] },
        { id: 6, text: "Do you have 6+ months of emergency savings outside this investment?", options: ["No, I don't have emergency savings", "Partial — only 1–3 months", "Yes, I have 6+ months", "Yes, I have 12+ months", "Yes, well beyond 12 months"] },
        { id: 7, text: "How stable is your income?", options: ["Very unstable", "Somewhat unstable", "Moderate stability", "Stable", "Very stable / multiple sources"] },
        { id: 8, text: "Have you invested in equities before?", options: ["Never", "Tried once", "Invested a few times", "Invest regularly", "Professional / daily trader"] },
        { id: 9, text: "What annual return do you expect?", options: ["Less than 3%", "3–5%", "5–8%", "8–12%", "More than 12%"] },
        { id: 10, text: "How do you feel about short-term volatility for long-term gains?", options: ["I hate it — I want stable value", "I dislike it but can tolerate a bit", "Neutral — I understand it's part of investing", "I accept it as necessary", "I embrace it — higher volatility means opportunity"] },
    ]

    const { data: questions } = useQuery({
        queryKey: ['quiz-questions'],
        queryFn: fetchQuizQuestions,
    })

    const quizQuestions = questions || fallbackQuestions
    const totalSteps = RESULT_STEP + 1
    const progress = ((step + 1) / totalSteps) * 100
    const currentAnswer = store.quizAnswers.find(a => a.question_id === step)?.answer

    const handleNext = () => {
        if (step === 0 && localName.trim()) {
            store.setUserName(localName.trim())
            setStep(1)
        } else if (step >= 1 && step <= 10 && currentAnswer) {
            setStep(step + 1)
        }
    }

    const handleSubmit = async () => {
        setIsSubmitting(true)
        try {
            const objInputs = {
                monthly_income: Number(objectiveForm.monthly_income) || 3000,
                monthly_expenses: Number(objectiveForm.monthly_expenses) || 2000,
                total_investable_assets: Number(objectiveForm.total_investable_assets) || 50000,
                investment_amount: Number(objectiveForm.investment_amount) || 10000,
                employment_type: objectiveForm.employment_type,
                time_horizon_years: Number(objectiveForm.time_horizon_years) || 10,
                has_emergency_fund: objectiveForm.has_emergency_fund,
            }

            store.setObjectiveInputs(objInputs)
            store.setInvestmentAmount(objInputs.investment_amount)

            const result = await submitRiskProfile({
                name: store.userName,
                quiz_answers: store.quizAnswers,
                objective_inputs: objInputs,
                uses_isa: store.usesIsa,
            }) as any

            store.setRiskProfile(result)
            setStep(RESULT_STEP)
        } catch (error) {
            // Fallback: compute locally if backend unavailable
            const avgAnswer = store.quizAnswers.reduce((s, a) => s + a.answer, 0) / 10
            const score = Math.round(1 + (avgAnswer - 1) / 4 * 9)
            const bands: Record<number, string> = {
                1: "Capital Preservation", 2: "Very Conservative", 3: "Conservative",
                4: "Moderately Conservative", 5: "Balanced", 6: "Moderately Aggressive",
                7: "Growth", 8: "Aggressive Growth", 9: "High Risk", 10: "Maximum Growth",
            }
            store.setRiskProfile({
                user_id: 1,
                subjective_score: score,
                objective_score: score,
                composite_score: score,
                risk_band: bands[score] || "Balanced",
                risk_score_int: score,
                time_horizon_years: Number(objectiveForm.time_horizon_years) || 10,
                uses_isa: store.usesIsa,
                description: `Your risk profile has been assessed as ${bands[score]}.`,
            })
            setStep(RESULT_STEP)
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <motion.div
            className="onboarding"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
        >
            <div className="onboarding__header">
                <div className="onboarding__logo">UK Robo Advisor</div>
                <div className="onboarding__progress-info">
                    <span className="font-mono text-secondary">
                        {step <= 10 ? `${step}/${10}` : step === OBJECTIVE_STEP ? 'Financial Profile' : 'Results'}
                    </span>
                </div>
            </div>

            <div className="progress-bar">
                <div className="progress-bar__fill" style={{ width: `${progress}%` }} />
            </div>

            <div className="onboarding__body">
                <AnimatePresence mode="wait">
                    {/* Step 0: Name */}
                    {step === 0 && (
                        <motion.div
                            key="name"
                            className="onboarding__step"
                            initial={{ opacity: 0, x: 40 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -40 }}
                            transition={{ duration: 0.3 }}
                        >
                            <h2 className="onboarding__question">What's your name?</h2>
                            <p className="onboarding__hint">We'll use this to personalise your experience.</p>
                            <input
                                className="input input--mono onboarding__name-input"
                                type="text"
                                placeholder="Enter your name"
                                value={localName}
                                onChange={e => setLocalName(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && handleNext()}
                                autoFocus
                            />
                            <button
                                className="btn btn--primary btn--lg onboarding__next-btn"
                                disabled={!localName.trim()}
                                onClick={handleNext}
                            >
                                Continue
                            </button>
                        </motion.div>
                    )}

                    {/* Steps 1-10: Quiz */}
                    {step >= 1 && step <= 10 && (
                        <motion.div
                            key={`q-${step}`}
                            className="onboarding__step"
                            initial={{ opacity: 0, x: 40 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -40 }}
                            transition={{ duration: 0.3 }}
                        >
                            <h2 className="onboarding__question">
                                {quizQuestions[step - 1]?.text}
                            </h2>
                            <div className="onboarding__options">
                                {quizQuestions[step - 1]?.options.map((option, i) => (
                                    <button
                                        key={i}
                                        className={`onboarding__option ${currentAnswer === i + 1 ? 'onboarding__option--selected' : ''}`}
                                        onClick={() => {
                                            store.setQuizAnswer(step, i + 1)
                                            // Auto-advance after brief delay
                                            setTimeout(() => {
                                                if (step < 10) setStep(step + 1)
                                                else setStep(OBJECTIVE_STEP)
                                            }, 300)
                                        }}
                                    >
                                        <span className="onboarding__option-num font-mono">{i + 1}</span>
                                        <span className="onboarding__option-text">{option}</span>
                                    </button>
                                ))}
                            </div>

                            <div className="onboarding__nav">
                                <button className="btn btn--ghost" onClick={() => setStep(step - 1)}>
                                    ← Back
                                </button>
                            </div>
                        </motion.div>
                    )}

                    {/* Step 11: Objective Inputs */}
                    {step === OBJECTIVE_STEP && (
                        <motion.div
                            key="objective"
                            className="onboarding__step"
                            initial={{ opacity: 0, x: 40 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -40 }}
                            transition={{ duration: 0.3 }}
                        >
                            <h2 className="onboarding__question">Financial Profile</h2>
                            <p className="onboarding__hint">This helps us assess your investment capacity objectively.</p>

                            <div className="onboarding__form-grid">
                                <div className="input-group">
                                    <label className="input-label">Monthly Income (£)</label>
                                    <input className="input input--mono" type="number" placeholder="3000"
                                        value={objectiveForm.monthly_income}
                                        onChange={e => setObjectiveForm(p => ({ ...p, monthly_income: e.target.value }))} />
                                </div>
                                <div className="input-group">
                                    <label className="input-label">Monthly Expenses (£)</label>
                                    <input className="input input--mono" type="number" placeholder="2000"
                                        value={objectiveForm.monthly_expenses}
                                        onChange={e => setObjectiveForm(p => ({ ...p, monthly_expenses: e.target.value }))} />
                                </div>
                                <div className="input-group">
                                    <label className="input-label">Total Investable Assets (£)</label>
                                    <input className="input input--mono" type="number" placeholder="50000"
                                        value={objectiveForm.total_investable_assets}
                                        onChange={e => setObjectiveForm(p => ({ ...p, total_investable_assets: e.target.value }))} />
                                </div>
                                <div className="input-group">
                                    <label className="input-label">Investment Amount (£)</label>
                                    <input className="input input--mono" type="number" placeholder="10000"
                                        value={objectiveForm.investment_amount}
                                        onChange={e => setObjectiveForm(p => ({ ...p, investment_amount: e.target.value }))} />
                                </div>
                                <div className="input-group">
                                    <label className="input-label">Employment Type</label>
                                    <select className="input" value={objectiveForm.employment_type}
                                        onChange={e => setObjectiveForm(p => ({ ...p, employment_type: e.target.value }))}>
                                        <option value="employed">Employed</option>
                                        <option value="self_employed">Self-Employed</option>
                                        <option value="retired">Retired</option>
                                        <option value="student">Student</option>
                                    </select>
                                </div>
                                <div className="input-group">
                                    <label className="input-label">Time Horizon (years)</label>
                                    <input className="input input--mono" type="number" min="1" max="50"
                                        value={objectiveForm.time_horizon_years}
                                        onChange={e => setObjectiveForm(p => ({ ...p, time_horizon_years: e.target.value }))} />
                                </div>
                                <div className="input-group">
                                    <label className="input-label">Emergency Fund</label>
                                    <select className="input" value={objectiveForm.has_emergency_fund}
                                        onChange={e => setObjectiveForm(p => ({ ...p, has_emergency_fund: e.target.value }))}>
                                        <option value="no">No emergency savings</option>
                                        <option value="partial">Partial (1–3 months)</option>
                                        <option value="yes">Yes (6+ months)</option>
                                    </select>
                                </div>
                                <div className="input-group">
                                    <label className="input-label">Invest via ISA?</label>
                                    <select className="input" value={store.usesIsa ? 'yes' : 'no'}
                                        onChange={e => store.setUsesIsa(e.target.value === 'yes')}>
                                        <option value="no">No</option>
                                        <option value="yes">Yes (£20,000 annual limit)</option>
                                    </select>
                                </div>
                            </div>

                            <div className="onboarding__nav">
                                <button className="btn btn--ghost" onClick={() => setStep(10)}>← Back</button>
                                <button
                                    className="btn btn--primary btn--lg"
                                    onClick={handleSubmit}
                                    disabled={isSubmitting}
                                >
                                    {isSubmitting ? 'Analysing...' : 'Calculate Risk Profile'}
                                </button>
                            </div>
                        </motion.div>
                    )}

                    {/* Step 12: Result */}
                    {step === RESULT_STEP && store.riskProfile && (
                        <motion.div
                            key="result"
                            className="onboarding__step onboarding__result"
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ duration: 0.5, type: 'spring' }}
                        >
                            <h2 className="onboarding__question">Your Risk Profile</h2>

                            <div className="onboarding__score-ring">
                                <svg viewBox="0 0 120 120" className="onboarding__gauge">
                                    <circle cx="60" cy="60" r="52" fill="none" stroke="var(--border)" strokeWidth="8" />
                                    <circle
                                        cx="60" cy="60" r="52" fill="none"
                                        stroke="var(--accent-blue)" strokeWidth="8"
                                        strokeDasharray={`${(store.riskProfile.risk_score_int / 10) * 327} 327`}
                                        strokeLinecap="round"
                                        transform="rotate(-90 60 60)"
                                        style={{ transition: 'stroke-dasharray 1s ease-out' }}
                                    />
                                </svg>
                                <div className="onboarding__score-text">
                                    <span className="onboarding__score-value font-mono">{store.riskProfile.risk_score_int}</span>
                                    <span className="onboarding__score-max font-mono">/10</span>
                                </div>
                            </div>

                            <div className="badge badge--blue onboarding__score-badge">
                                {store.riskProfile.risk_band}
                            </div>

                            <p className="onboarding__result-desc">
                                {store.riskProfile.description}
                            </p>

                            <div className="onboarding__result-details">
                                <div className="stat">
                                    <span className="stat__label">Subjective</span>
                                    <span className="stat__value font-mono">{store.riskProfile.subjective_score}</span>
                                </div>
                                <div className="stat">
                                    <span className="stat__label">Objective</span>
                                    <span className="stat__value font-mono">{store.riskProfile.objective_score}</span>
                                </div>
                                <div className="stat">
                                    <span className="stat__label">Composite</span>
                                    <span className="stat__value font-mono">{store.riskProfile.composite_score}</span>
                                </div>
                            </div>

                            <button
                                className="btn btn--primary btn--lg"
                                onClick={() => navigate('/assets')}
                            >
                                Choose Asset Classes →
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </motion.div>
    )
}
