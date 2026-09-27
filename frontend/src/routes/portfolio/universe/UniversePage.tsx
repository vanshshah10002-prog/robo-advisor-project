import { clsx } from 'clsx'
import { useConstruction, useUniverse } from '@/api/queries'
import type { ConstructionSnapshot, Universe } from '@/api/schemas'
import { AllocationBar, CompareBars, Heatmap } from '@/charts'
import { date, decimal } from '@/lib/format'
import { CATEGORICAL, CHART_INK } from '@/lib/palette'
import { usePageTitle } from '@/lib/usePageTitle'
import { Button } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import { sectionTitle, usePortfolio } from '../context'
import styles from '../Portfolio.module.css'
import { BlockList } from './BlockList'
import { blockRows, heldCorrelations, regionShares, riskSentence, universeSentence, type BlockRow } from './model'

/** Every building block, what this portfolio holds of each and why, and how the pieces behave together. */
export default function UniversePage() {
    const { id } = usePortfolio()
    usePageTitle(sectionTitle(id, 'Asset universe'))
    const universe = useUniverse(id)
    const construction = useConstruction(id)

    if (universe.isPending || construction.isPending) return <p className={styles.loading} aria-busy="true">Loading the building blocks…</p>
    if (universe.isError) {
        return (
            <Notice tone="error" title="The building blocks did not load" action={<Button size="sm" variant="secondary" onClick={() => universe.refetch()}>Try again</Button>}>
                {universe.error.message}
            </Notice>
        )
    }
    const snapshot = construction.data?.snapshot ?? null
    return <Body universe={universe.data} snapshot={snapshot} />
}

function Body({ universe, snapshot }: { universe: Universe; snapshot: ConstructionSnapshot | null }) {
    const rows = blockRows(universe, snapshot)
    return (
        <article className={clsx(styles.section, 'stagger')} aria-labelledby="universe-title">
            <header className={styles.head}>
                <h1 id="universe-title" className={styles.title}>
                    {universeSentence(rows)}
                </h1>
                <p className={styles.lead}>
                    Every portfolio is built from the same {rows.length} building blocks. Each has a job, a limit, and a first-choice fund
                    with alternatives. How much of each is held depends on the risk level.
                </p>
            </header>
            {snapshot ? (
                <RiskShares rows={rows} snapshot={snapshot} />
            ) : (
                <Notice tone="info" title="The estimates behind this portfolio were not recorded">
                    It was opened before they were kept, so the share of risk and the correlations cannot be shown.
                </Notice>
            )}
            <BlockList title="Growth" rows={rows.filter((r) => r.sleeve === 'growth')} />
            <BlockList title="Defensive" rows={rows.filter((r) => r.sleeve === 'defensive')} />
            <Regions rows={rows} universe={universe} />
            {snapshot && <Correlations rows={rows} snapshot={snapshot} />}
        </article>
    )
}

function estimatesNote(snapshot: ConstructionSnapshot): string {
    return (
        `Estimates made when the portfolio was opened, on ${date(snapshot.as_of)}. Volatilities include a ${decimal(snapshot.vol_calibration, 2)}× ` +
        'allowance, because testing found real swings ran 10–20% larger than the raw estimates.'
    )
}

function RiskShares({ rows, snapshot }: { rows: readonly BlockRow[]; snapshot: ConstructionSnapshot }) {
    const held = rows.filter((r) => r.held !== null && r.weight !== null && r.riskShare !== null).sort((a, b) => (b.riskShare ?? 0) - (a.riskShare ?? 0))
    return (
        <CompareBars
            title="Where the risk comes from"
            summary={riskSentence(rows) ?? undefined}
            provenance="estimated"
            series={[
                { label: 'Share of the money', colour: CHART_INK.axis },
                { label: 'Share of the risk', colour: CATEGORICAL[0] },
            ]}
            items={held.map((r) => ({ key: r.assetClass, label: r.name, detail: r.held?.ticker, values: [r.weight ?? 0, r.riskShare ?? 0] }))}
            notes={`Share of the risk is each holding's part of the portfolio's expected swings, allowing for how the funds move together. ${estimatesNote(snapshot)}`}
        />
    )
}

function Regions({ rows, universe }: { rows: readonly BlockRow[]; universe: Universe }) {
    const regions = regionShares(rows, universe)
    if (regions.length === 0) return null
    return (
        <AllocationBar
            title="Where the shares are"
            summary="Of the money in shares, the part in each region."
            provenance="measured"
            items={regions.map((r) => ({ ...r, sleeve: 'growth' as const }))}
        />
    )
}

function Correlations({ rows, snapshot }: { rows: readonly BlockRow[]; snapshot: ConstructionSnapshot }) {
    const { labels, matrix } = heldCorrelations(snapshot, rows)
    return (
        <Heatmap
            title="How the funds move together"
            summary="1 means two funds always move together; 0 means they are unrelated. Darker cells move together more."
            provenance="estimated"
            labels={labels}
            matrix={matrix}
            notes={`From monthly returns in pounds, as estimated when the portfolio was built on ${date(snapshot.as_of)}.`}
        />
    )
}

