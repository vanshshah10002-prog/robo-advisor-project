/** Archiving from the list: the action on each row, and what happened. */
import { useState } from 'react'
import { useSetArchived } from '@/api/queries'
import type { PortfolioSummary } from '@/api/schemas'
import type { Column } from '@/charts'
import { useIdentity } from '@/store/session'
import { Button } from '@/ui/Button'
import { portfolioName } from './model'

export type Outcome = { row: PortfolioSummary; archived: boolean; error?: string }

/**
 * Archives or restores a row and remembers what happened, for the notice.
 * Archiving the portfolio "your portfolio" points at moves that pointer to
 * the newest one left on the list, or clears it.
 */
export function useArchiving(active: readonly PortfolioSummary[] | undefined) {
    const setArchived = useSetArchived()
    const [outcome, setOutcome] = useState<Outcome | null>(null)

    const run = (row: PortfolioSummary, archived: boolean) => {
        if (setArchived.isPending) return
        setArchived.mutate(
            { portfolioId: row.portfolio_id, archived },
            {
                onSuccess: () => {
                    const { lastPortfolioId, setLastPortfolio } = useIdentity.getState()
                    if (archived && lastPortfolioId === row.portfolio_id) {
                        setLastPortfolio(active?.find((r) => r.portfolio_id !== row.portfolio_id)?.portfolio_id ?? null)
                    }
                    setOutcome({ row, archived })
                },
                onError: (error) => setOutcome({ row, archived, error: error.message }),
            },
        )
    }
    const pendingId = setArchived.isPending ? (setArchived.variables?.portfolioId ?? null) : null
    return { outcome, pendingId, archive: (row: PortfolioSummary) => run(row, true), restore: (row: PortfolioSummary) => run(row, false) }
}

/** While one row is being archived or restored, its button shows it is working and the others wait. */
export const rowAction = (id: number, pendingId: number | null) => ({ loading: pendingId === id, disabled: pendingId !== null && pendingId !== id })

export const actionsLabel = <span className="visually-hidden">Actions</span>

export function archiveColumn(onArchive: (row: PortfolioSummary) => void, pendingId: number | null): Column<PortfolioSummary> {
    return {
        key: 'archive',
        label: actionsLabel,
        render: (r) => (
            <Button size="sm" variant="quiet" aria-label={`Archive ${portfolioName(r)}`} {...rowAction(r.portfolio_id, pendingId)} onClick={() => onArchive(r)}>
                Archive
            </Button>
        ),
    }
}
