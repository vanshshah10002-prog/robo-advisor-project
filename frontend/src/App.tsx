import { lazy, Suspense } from 'react'
import { Outlet, Routes, Route } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import Onboarding from './pages/Onboarding/Onboarding'
import AssetSelection from './pages/AssetSelection/AssetSelection'
import InvestmentInput from './pages/InvestmentInput/InvestmentInput'
import PortfolioBuilder from './pages/PortfolioBuilder/PortfolioBuilder'
import Review from './pages/Review/Review'
import Dashboard from './pages/Dashboard/Dashboard'
import Landing from './pages/Landing/Landing'
import PortfolioHistory from './pages/PortfolioHistory/PortfolioHistory'
import AppShell from './routes/AppShell'

const Styleguide = lazy(() => import('./routes/styleguide/Styleguide'))

/** Screens not yet rebuilt keep their own headers; this only adds the skip link and small print. */
function LegacyLayout() {
    return (
        <div className="app">
            <a className="skip-link" href="#main">
                Skip to content
            </a>
            <main id="main" tabIndex={-1}>
                <AnimatePresence mode="wait">
                    <Outlet />
                </AnimatePresence>
            </main>

            <footer className="disclaimer-footer">
                For education and personal use only. Not authorised or regulated by the FCA, and not financial
                advice. The value of investments can fall as well as rise, and you may get back less than you put in.
            </footer>
        </div>
    )
}

function App() {
    return (
        <Routes>
            <Route element={<LegacyLayout />}>
                <Route path="/" element={<Landing />} />
                <Route path="/onboarding" element={<Onboarding />} />
                <Route path="/assets" element={<AssetSelection />} />
                <Route path="/invest" element={<InvestmentInput />} />
                <Route path="/builder" element={<PortfolioBuilder />} />
                <Route path="/review" element={<Review />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/history" element={<PortfolioHistory />} />
            </Route>
            <Route element={<AppShell />}>
                <Route
                    path="/styleguide"
                    element={
                        <Suspense fallback={null}>
                            <Styleguide />
                        </Suspense>
                    }
                />
            </Route>
        </Routes>
    )
}

export default App
