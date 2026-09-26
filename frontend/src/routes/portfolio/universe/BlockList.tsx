import { clsx } from 'clsx'
import type { UniverseFund } from '@/api/schemas'
import { EMPTY, moneyCompact, percent } from '@/lib/format'
import styles from './Universe.module.css'
import type { BlockRow } from './model'

/** A registry link is shown only when it is a plain https address. */
const safeUrl = (url: string | null) => (url && /^https:\/\//i.test(url) ? url : null)

/** One side of the portfolio: its blocks, held ones first. */
export function BlockList({ title, rows }: { title: string; rows: readonly BlockRow[] }) {
    const held = rows.filter((r) => r.held !== null).length
    const id = `blocks-${title.toLowerCase()}`
    return (
        <section className={styles.group} aria-labelledby={id}>
            <h2 id={id} className={styles.groupTitle}>
                {title} <span className={styles.count}>{held} of {rows.length} held</span>
            </h2>
            <ul className={styles.blocks}>
                {rows.map((r) => (
                    <Block key={r.assetClass} row={r} />
                ))}
            </ul>
        </section>
    )
}

function Block({ row }: { row: BlockRow }) {
    const held = row.held !== null
    return (
        <li className={clsx(styles.block, !held && styles.unheld)}>
            <div className={styles.blockHead}>
                <h3 className={styles.blockName}>{row.name}</h3>
                <span className={styles.blockWeight}>{held ? percent(row.weight) : 'Not held'}</span>
            </div>
            <p className={styles.description}>{row.description}</p>
            {held && <Figures row={row} />}
            <p className={styles.rule}>
                <span className={styles.ruleLabel}>Limit</span> {row.rule}
            </p>
            {row.held && <Fund fund={row.held} />}
            {row.note && <p className={styles.blockNote}>{row.note}</p>}
            {row.alternatives.length > 0 && (
                <details className={styles.alternatives}>
                    <summary>
                        {held ? 'Other funds for this block' : 'Funds for this block'} ({row.alternatives.length})
                    </summary>
                    <ul>
                        {row.alternatives.map((f) => (
                            <li key={f.ticker}>
                                <Fund fund={f} />
                            </li>
                        ))}
                    </ul>
                </details>
            )}
        </li>
    )
}

function Figures({ row }: { row: BlockRow }) {
    const figures = [
        ['Target', percent(row.target)],
        ['Expected return', row.expectedReturn === null ? EMPTY : `${percent(row.expectedReturn)} a year`],
        ['Typical yearly swing', row.volatility === null ? EMPTY : `±${percent(row.volatility)}`],
        ['Share of the risk', row.riskShare === null ? EMPTY : percent(row.riskShare)],
    ] as const
    return (
        <dl className={styles.figures}>
            {figures.map(([label, value]) => (
                <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                </div>
            ))}
        </dl>
    )
}

/** A fund in one line of facts: name, ticker, ISIN, yearly cost, size, domicile, factsheet. */
function Fund({ fund }: { fund: UniverseFund }) {
    const url = safeUrl(fund.factsheet_url)
    const facts = [
        fund.ticker,
        fund.isin,
        `${percent(fund.expense_ratio, 2)} a year`,
        fund.fund_size_gbp_mm === null ? null : `${moneyCompact(fund.fund_size_gbp_mm * 1_000_000)} fund`,
        fund.domicile,
    ].filter((f): f is string => Boolean(f))
    return (
        <p className={styles.fund}>
            <span className={styles.fundName}>{fund.name}</span>
            <span className={styles.facts}>
                {facts.join(' · ')}
                {url && (
                    <>
                        {' · '}
                        <a href={url} target="_blank" rel="noreferrer">
                            Factsheet<span className="visually-hidden"> for {fund.name} (opens in a new tab)</span>
                        </a>
                    </>
                )}
            </span>
        </p>
    )
}

