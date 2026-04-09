import { Routes, Route } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import Onboarding from './pages/Onboarding/Onboarding'
import AssetSelection from './pages/AssetSelection/AssetSelection'
import InvestmentInput from './pages/InvestmentInput/InvestmentInput'
import PortfolioBuilder from './pages/PortfolioBuilder/PortfolioBuilder'
import Review from './pages/Review/Review'
import Dashboard from './pages/Dashboard/Dashboard'
import Landing from './pages/Landing/Landing'
import PortfolioHistory from './pages/PortfolioHistory/PortfolioHistory'

function App() {
    return (
        <div className="app">
            <AnimatePresence mode="wait">
                <Routes>
                    <Route path="/" element={<Landing />} />
                    <Route path="/onboarding" element={<Onboarding />} />
                    <Route path="/assets" element={<AssetSelection />} />
                    <Route path="/invest" element={<InvestmentInput />} />
                    <Route path="/builder" element={<PortfolioBuilder />} />
                    <Route path="/review" element={<Review />} />
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/history" element={<PortfolioHistory />} />
                </Routes>
            </AnimatePresence>

            <footer className="disclaimer-footer">
                This application is for educational/personal use only. Not registered with the FCA.
                Not financial advice. Consult a qualified financial advisor before investing.
            </footer>
        </div>
    )
}

export default App
