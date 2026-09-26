import { lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useIdentity } from './store/session'
import AppShell from './routes/AppShell'

// Every page is its own chunk: the first visit downloads only the page it lands on.
const LandingPage = lazy(() => import('./routes/landing/LandingPage'))
const StartLayout = lazy(() => import('./routes/start/StartLayout'))
const GoalsPage = lazy(() => import('./routes/start/GoalsPage'))
const LossesPage = lazy(() => import('./routes/start/LossesPage'))
const FinancesPage = lazy(() => import('./routes/start/FinancesPage'))
const ResultPage = lazy(() => import('./routes/start/ResultPage'))
const ProposalPage = lazy(() => import('./routes/proposal/ProposalPage'))
const PortfolioLayout = lazy(() => import('./routes/portfolio/PortfolioLayout'))
const OverviewPage = lazy(() => import('./routes/portfolio/overview/OverviewPage'))
const PerformancePage = lazy(() => import('./routes/portfolio/performance/PerformancePage'))
const UniversePage = lazy(() => import('./routes/portfolio/universe/UniversePage'))
const OutlookPage = lazy(() => import('./routes/portfolio/outlook/OutlookPage'))
const ActivityPage = lazy(() => import('./routes/portfolio/activity/ActivityPage'))
const PortfoliosPage = lazy(() => import('./routes/portfolio/PortfoliosPage'))
const Styleguide = lazy(() => import('./routes/styleguide/Styleguide'))
const NotFound = lazy(() => import('./routes/NotFound'))

/** The old dashboard showed the last portfolio; send its links there. */
function LastPortfolio() {
    const lastPortfolioId = useIdentity((s) => s.lastPortfolioId)
    return <Navigate to={lastPortfolioId === null ? '/portfolios' : `/portfolio/${lastPortfolioId}`} replace />
}

export default function App() {
    return (
        <Routes>
            <Route element={<AppShell />}>
                <Route index element={<LandingPage />} />
                <Route path="start" element={<StartLayout />}>
                    <Route index element={<GoalsPage />} />
                    <Route path="losses" element={<LossesPage />} />
                    <Route path="finances" element={<FinancesPage />} />
                    <Route path="result" element={<ResultPage />} />
                </Route>
                <Route path="proposal" element={<ProposalPage />} />
                <Route path="portfolios" element={<PortfoliosPage />} />
                <Route path="portfolio/:id" element={<PortfolioLayout />}>
                    <Route index element={<OverviewPage />} />
                    <Route path="performance" element={<PerformancePage />} />
                    <Route path="universe" element={<UniversePage />} />
                    <Route path="outlook" element={<OutlookPage />} />
                    <Route path="activity" element={<ActivityPage />} />
                </Route>
                <Route path="styleguide" element={<Styleguide />} />

                {/* Addresses from the previous version of the app. */}
                <Route path="onboarding" element={<Navigate to="/start" replace />} />
                {['assets', 'invest', 'builder', 'review'].map((path) => (
                    <Route key={path} path={path} element={<Navigate to="/proposal" replace />} />
                ))}
                <Route path="history" element={<Navigate to="/portfolios" replace />} />
                <Route path="dashboard" element={<LastPortfolio />} />

                <Route path="*" element={<NotFound />} />
            </Route>
        </Routes>
    )
}
