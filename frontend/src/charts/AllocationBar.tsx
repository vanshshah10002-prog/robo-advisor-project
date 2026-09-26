import { clsx } from 'clsx'
import { useMemo, type PointerEvent } from 'react'
import type { Sleeve } from '@/api/schemas'
import { money, percent } from '@/lib/format'
import { sleeveColours } from '@/lib/palette'
import type { ProvenanceKind } from '@/ui/provenance'
import { ChartFrame } from './ChartFrame'
import { DataTable, FundCell, type Column } from './DataTable'
import { useCursor, useElementWidth } from './hooks'
import { Key } from './Legend'
import { cumulativeStarts, describeRows, orderAllocation, sleeveTotals, type AllocationItem } from './model'
import { Announce, ChartTooltip, type TooltipRow } from './Tooltip'
import styles from './AllocationBar.module.css'

export interface AllocationBarProps {
    items: readonly AllocationItem[]
    title: string
    summary?: string
    provenance?: ProvenanceKind
    notes?: string
    pending?: boolean
}

const SLEEVES: readonly Sleeve[] = ['growth', 'defensive']
const SLEEVE_NAME: Record<Sleeve, string> = { growth: 'Growth', defensive: 'Defensive' }
/** Tooltip sits just under the 40px strip. */
const TOOLTIP_TOP = 48

/**
 * A single 100% strip of holdings, with the growth/defensive split bracketed
 * above it and every holding listed below. Hover or arrow keys read a segment.
 */
export function AllocationBar({ items, title, summary, provenance, notes, pending }: AllocationBarProps) {
    const ordered = useMemo(() => orderAllocation(items), [items])
    const colours = useMemo(() => sleeveColours(ordered.map((i) => i.sleeve)), [ordered])
    const totals = sleeveTotals(ordered)
    const hasValues = ordered.some((i) => typeof i.value === 'number')
    const total = ordered.reduce((sum, i) => sum + (i.value ?? 0), 0)

    return (
        <ChartFrame
            title={title}
            summary={summary}
            provenance={provenance}
            notes={notes}
            pending={pending}
            empty={ordered.length === 0 ? 'Nothing to show yet.' : undefined}
            table={
                <DataTable
                    caption={title}
                    columns={allocationColumns(hasValues)}
                    rows={ordered}
                    rowKey={(i) => i.key}
                    footer={['Total', '', percent(1, 0), ...(hasValues ? [money(total)] : [])]}
                />
            }
        >
            <SleeveBrackets totals={totals} />
            <AllocationStrip items={ordered} colours={colours} label={allocationLabel(title, totals, ordered.length)} hasValues={hasValues} />
            <HoldingList items={ordered} colours={colours} />
        </ChartFrame>
    )
}

function SleeveBrackets({ totals }: { totals: Record<Sleeve, number> }) {
    return (
        <div className={styles.brackets} aria-hidden="true">
            {SLEEVES.filter((s) => totals[s] > 0).map((s) => (
                <span key={s} className={styles.bracket} style={{ flexGrow: totals[s] }}>
                    <span className={styles.bracketName}>{SLEEVE_NAME[s]}</span>
                    <span className={styles.bracketShare}>{percent(totals[s], 0)}</span>
                </span>
            ))}
        </div>
    )
}

interface AllocationStripProps {
    items: readonly AllocationItem[]
    colours: readonly string[]
    label: string
    hasValues: boolean
}

function AllocationStrip({ items, colours, label, hasValues }: AllocationStripProps) {
    const [ref, width] = useElementWidth<HTMLDivElement>()
    const cursor = useCursor(items.length)
    const starts = cumulativeStarts(items)
    const i = cursor.index
    const active = i === null ? null : items[i]
    const rows = active ? segmentRows(active, hasValues) : []

    const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
        const box = e.currentTarget.getBoundingClientRect()
        const at = (e.clientX - box.left) / (box.width || width)
        const hit = starts.findIndex((s, k) => at >= s && at < s + items[k].weight)
        cursor.point(hit === -1 ? items.length - 1 : hit)
    }

    return (
        <div className={styles.plot} ref={ref}>
            <div className={styles.strip} role="img" aria-label={label} {...cursor.keyboard} onPointerMove={onPointerMove} onPointerLeave={() => cursor.point(null)}>
                {items.map((item, k) => (
                    <span
                        key={item.key}
                        className={clsx(styles.segment, i !== null && i !== k && styles.dim)}
                        style={{ flexGrow: item.weight, background: colours[k] }}
                    />
                ))}
            </div>
            {active && i !== null && (
                <ChartTooltip title={segmentTitle(active)} rows={rows} x={(starts[i] + active.weight / 2) * width} y={TOOLTIP_TOP} width={width} />
            )}
            <Announce text={active && cursor.fromKeyboard ? describeRows(active.label, rows) : ''} />
        </div>
    )
}

function HoldingList({ items, colours }: { items: readonly AllocationItem[]; colours: readonly string[] }) {
    return (
        <ul className={styles.list}>
            {items.map((item, k) => (
                <li key={item.key}>
                    <Key colour={colours[k]} />
                    <span className={styles.itemName}>
                        {item.label}
                        {item.detail && <span className={styles.itemDetail}>{item.detail}</span>}
                    </span>
                    <span className={styles.itemShare}>{percent(item.weight)}</span>
                </li>
            ))}
        </ul>
    )
}

const segmentTitle = (item: AllocationItem) => (item.detail ? `${item.label} · ${item.detail}` : item.label)

function segmentRows(item: AllocationItem, hasValues: boolean): TooltipRow[] {
    return [
        { key: 'weight', label: 'Share', value: percent(item.weight) },
        ...(hasValues ? [{ key: 'value', label: 'Value', value: money(item.value) }] : []),
        { key: 'sleeve', label: 'Sleeve', value: SLEEVE_NAME[item.sleeve] },
    ]
}

function allocationLabel(title: string, totals: Record<Sleeve, number>, count: number): string {
    const split = SLEEVES.filter((s) => totals[s] > 0)
        .map((s) => `${SLEEVE_NAME[s].toLowerCase()} ${percent(totals[s], 0)}`)
        .join(', ')
    return `${title}: ${split}, across ${count} holdings. Use the arrow keys to read each one, or switch to the table.`
}

function allocationColumns(hasValues: boolean): Column<AllocationItem>[] {
    const columns: Column<AllocationItem>[] = [
        { key: 'holding', label: 'Holding', render: (i) => <FundCell name={i.label} ticker={i.detail} /> },
        { key: 'sleeve', label: 'Sleeve', render: (i) => SLEEVE_NAME[i.sleeve] },
        { key: 'weight', label: 'Share', numeric: true, render: (i) => percent(i.weight) },
    ]
    return hasValues ? [...columns, { key: 'value', label: 'Value', numeric: true, render: (i) => money(i.value) }] : columns
}
