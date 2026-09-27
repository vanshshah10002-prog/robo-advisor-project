import { useOutletContext } from 'react-router-dom'
import type { Performance, PortfolioDetail } from '@/api/schemas'

/** What the workspace has already loaded, shared with each of its sections. */
export interface PortfolioContext {
    id: number
    performance: Performance
    /** Undefined while it loads: risk level, account and monthly amount. */
    detail: PortfolioDetail | undefined
}

export const usePortfolio = () => useOutletContext<PortfolioContext>()

/** The workspace's sections, in the order of its navigation. */
export const SECTIONS = [
    { path: '', label: 'Overview' },
    { path: 'performance', label: 'Performance' },
    { path: 'universe', label: 'Asset universe' },
    { path: 'outlook', label: 'Outlook' },
    { path: 'activity', label: 'Activity' },
] as const

/** "Performance · Portfolio 20", or "Portfolio 20" for the overview. */
export const sectionTitle = (id: number, label?: string) => (label ? `${label} · Portfolio ${id}` : `Portfolio ${id}`)
