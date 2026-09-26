import { ArrowRight, CheckCircle, Warning } from '@phosphor-icons/react'
import { useState, type ReactNode } from 'react'
import { contrast } from '@/lib/contrast'
import { money, percent, signedPercent } from '@/lib/format'
import { CATEGORICAL, DEFENSIVE_RAMP, GROWTH_RAMP, allocationColours, sleeveOf } from '@/lib/palette'
import { Button } from '@/ui/Button'
import { Field, TextInput } from '@/ui/Field'
import { Delta, Stat, StatGroup } from '@/ui/Stat'
import { Provenance, Tag } from '@/ui/Tag'
import { SPECIMEN_HOLDINGS, SPECIMEN_TOTAL } from './specimen'
import styles from './Styleguide.module.css'

const PAPER = '#f7f4ed'

const SWATCHES = [
    { group: 'Surfaces', items: [['Paper', 'color-paper', PAPER], ['Sheet', 'color-sheet', '#fdfbf7'], ['Sunk', 'color-sunk', '#ede9e1']] },
    { group: 'Ink', items: [['Ink', 'color-ink', '#1f1b16'], ['Ink 2', 'color-ink-2', '#534c44'], ['Ink 3', 'color-ink-3', '#69625a']] },
    { group: 'Rules', items: [['Hairline', 'color-rule', '#dad3c9'], ['Control edge', 'color-rule-strong', '#8d857a']] },
    { group: 'Meaning', items: [['Action', 'color-accent', '#284e99'], ['Loss', 'color-loss', '#9e2c2c'], ['OK', 'color-ok', '#266739'], ['Caution', 'color-warn', '#945a00']] },
] as const

function grade(ratio: number): string {
    if (ratio >= 7) return 'AAA text'
    if (ratio >= 4.5) return 'AA text'
    if (ratio >= 3) return 'UI 3:1'
    return 'Decorative'
}

function Section({ id, title, intro, children }: { id: string; title: string; intro: string; children: ReactNode }) {
    return (
        <section className={styles.section} aria-labelledby={id}>
            <header className={styles.rail}>
                <h2 id={id}>{title}</h2>
                <p>{intro}</p>
            </header>
            <div className={styles.body}>{children}</div>
        </section>
    )
}

function Swatches() {
    return (
        <div className={styles.swatchGroups}>
            {SWATCHES.map(({ group, items }) => (
                <div key={group}>
                    <h3 className="label">{group}</h3>
                    <ul className={styles.swatches}>
                        {items.map(([name, token, hex]) => {
                            const ratio = contrast(hex, PAPER)
                            return (
                                <li key={token} className={styles.swatch}>
                                    <span className={styles.chip} style={{ background: hex }} />
                                    <span className={styles.swatchName}>{name}</span>
                                    <code className={styles.swatchMeta}>--{token}</code>
                                    <span className={styles.swatchMeta}>
                                        {hex} · {ratio.toFixed(1)}:1 {grade(ratio)}
                                    </span>
                                </li>
                            )
                        })}
                    </ul>
                </div>
            ))}
        </div>
    )
}

function AllocationStrip() {
    const colours = allocationColours(SPECIMEN_HOLDINGS.map((h) => h.assetClass))
    return (
        <figure className={styles.figure}>
            <figcaption className={styles.figcaption}>
                <span>Allocation, balanced portfolio</span>
                <span className="label">Illustrative</span>
            </figcaption>
            <div className={styles.strip} role="img" aria-label="Growth 50%, defensive 50%. Detailed in the list below.">
                {SPECIMEN_HOLDINGS.map((h, i) => (
                    <span key={h.ticker} style={{ flexGrow: h.weight, background: colours[i] }} />
                ))}
            </div>
            <ul className={styles.legend}>
                {SPECIMEN_HOLDINGS.map((h, i) => (
                    <li key={h.ticker}>
                        <span className={styles.key} style={{ background: colours[i] }} aria-hidden="true" />
                        <span>{h.label}</span>
                        <span className={styles.legendSleeve}>{sleeveOf(h.assetClass)}</span>
                        <span>{percent(h.weight, 0)}</span>
                    </li>
                ))}
            </ul>
        </figure>
    )
}

function Ramp({ name, colours }: { name: string; colours: readonly string[] }) {
    return (
        <div className={styles.ramp}>
            <span className="label">{name}</span>
            <div className={styles.rampSteps}>
                {colours.map((c, i) => (
                    <span key={c} style={{ background: c }} title={c}>
                        <span className="visually-hidden">
                            Step {i + 1}: {c}
                        </span>
                    </span>
                ))}
            </div>
        </div>
    )
}

function StatementTable() {
    return (
        <figure className={styles.figure}>
            <figcaption className={styles.figcaption}>
                <span>Holdings</span>
                <span className="label">Illustrative figures</span>
            </figcaption>
            <div className={styles.tableScroll}>
                <table className={styles.table}>
                    <thead>
                        <tr>
                            <th scope="col">Fund</th>
                            <th scope="col">Sleeve</th>
                            <th scope="col" className={styles.numCol}>Value</th>
                            <th scope="col" className={styles.numCol}>Weight</th>
                            <th scope="col" className={styles.numCol}>Return</th>
                        </tr>
                    </thead>
                    <tbody>
                        {SPECIMEN_HOLDINGS.map((h) => (
                            <tr key={h.ticker}>
                                <th scope="row">
                                    <span className={styles.fund}>{h.name}</span>
                                    <span className={styles.ticker}>{h.ticker}</span>
                                </th>
                                <td>{sleeveOf(h.assetClass)}</td>
                                <td className={styles.numCol}>{money(h.value)}</td>
                                <td className={styles.numCol}>{percent(h.weight, 0)}</td>
                                <td className={styles.numCol}>
                                    <Delta value={h.returnPct} />
                                </td>
                            </tr>
                        ))}
                    </tbody>
                    <tfoot>
                        <tr>
                            <th scope="row">Total</th>
                            <td />
                            <td className={styles.numCol}>{money(SPECIMEN_TOTAL)}</td>
                            <td className={styles.numCol}>{percent(1, 0)}</td>
                            <td className={styles.numCol}>
                                <Delta value={0.245} />
                            </td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </figure>
    )
}

function Controls() {
    const [amount, setAmount] = useState('100000')
    const [busy, setBusy] = useState(false)
    const invalid = amount.trim() === '' || Number(amount) <= 0 || Number.isNaN(Number(amount))

    return (
        <div className={styles.controls}>
            <div className={styles.buttonRow}>
                <Button trailingIcon={<ArrowRight weight="bold" />}>Build my portfolio</Button>
                <Button variant="secondary">Compare risk levels</Button>
                <Button variant="quiet">What does this mean?</Button>
            </div>
            <div className={styles.buttonRow}>
                <Button loading={busy} onClick={() => { setBusy(true); window.setTimeout(() => setBusy(false), 1600) }}>
                    Run simulation
                </Button>
                <Button disabled>Rebalance</Button>
                <Button size="sm" variant="secondary">Small</Button>
            </div>
            <div className={styles.fields}>
                <Field
                    label="Amount to invest (£)"
                    hint="The lump sum you put in today. You can add more later."
                    error={invalid ? 'Enter an amount above £0.' : undefined}
                >
                    {(c) => (
                        <TextInput {...c} prefix="£" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
                    )}
                </Field>
                <Field label="Time horizon" hint="When you expect to need most of the money.">
                    {(c) => <TextInput {...c} suffix="years" inputMode="numeric" defaultValue="15" />}
                </Field>
                <Field label="Portfolio name" optional>
                    {(c) => <TextInput {...c} placeholder="e.g. House deposit" />}
                </Field>
            </div>
        </div>
    )
}

export default function Styleguide() {
    return (
        <article className={styles.page}>
            <header className={styles.masthead}>
                <div className={styles.dateline}>
                    <span className="label">Design system</span>
                    <span className="label">Light theme · September 2026</span>
                </div>
                <h1 className={styles.title}>
                    The <em>Statement</em>
                </h1>
                <p className={styles.lead}>
                    A portfolio should read like a well-kept statement: every figure in its column, every colour
                    standing for something, and every number saying where it came from.
                </p>
                <ol className={styles.principles}>
                    <li>
                        <strong>Colour is meaning.</strong> Growth holdings are verdigris, defensive holdings ochre,
                        losses claret. Nothing else gets colour.
                    </li>
                    <li>
                        <strong>Ranges, not points.</strong> The future is shown as a spread of outcomes with the
                        middle marked, never a single confident line.
                    </li>
                    <li>
                        <strong>Say where it came from.</strong> Each figure is <Provenance kind="measured" />,{' '}
                        <Provenance kind="simulated" /> or <Provenance kind="estimated" />.
                    </li>
                </ol>
            </header>

            <Section id="sg-colour" title="Paper and ink" intro="Contrast is measured against paper and enforced by tests, so it cannot drift.">
                <Swatches />
            </Section>

            <Section id="sg-holdings" title="Holdings colour" intro="Two ordinal ramps, chosen to stay distinct under red–green colour blindness. Segments are always separated and labelled.">
                <AllocationStrip />
                <div className={styles.ramps}>
                    <Ramp name="Growth" colours={GROWTH_RAMP} />
                    <Ramp name="Defensive" colours={DEFENSIVE_RAMP} />
                    <Ramp name="Comparison (fixed order)" colours={CATEGORICAL} />
                </div>
            </Section>

            <Section id="sg-type" title="Type" intro="Newsreader for headlines and headline figures; Schibsted Grotesk for everything you read or operate.">
                <div className={styles.typeScale}>
                    <p className={styles.specimenXl}>{money(SPECIMEN_TOTAL)}</p>
                    <p className={styles.specimen3xl}>Your money, five years on</p>
                    <p className={styles.specimen2xl}>How the portfolio is built</p>
                    <p className={styles.specimenXl2}>Growth and defensive, side by side</p>
                    <p className={styles.specimenBody}>
                        Body text is set at 16px with a 66-character measure. Figures inside sentences, like{' '}
                        {money(12_452)} or {signedPercent(0.045)}, use the same lining numerals as the tables.
                    </p>
                    <p className="label">Label · 12px · uppercase · tracked</p>
                </div>
            </Section>

            <Section id="sg-figures" title="Figures" intro="Tabular numerals, right-aligned, signed. Totals sit under a double rule, as on paper.">
                <StatementTable />
            </Section>

            <Section id="sg-stats" title="Headline figures" intro="The one number that matters is large; everything else steps down. Figures here are illustrative.">
                <StatGroup className={styles.stats}>
                    <Stat size="lg" label="Portfolio value" provenance="measured" value={money(SPECIMEN_TOTAL)} detail={<><Delta value={0.245} /> since you started</>} />
                    <Stat label="In 15 years, middle outcome" provenance="simulated" value={money(238_400)} detail="1 in 10 below £161k · 1 in 10 above £352k" />
                    <Stat label="Expected return" provenance="estimated" value={percent(0.048)} detail="a year, before inflation" />
                </StatGroup>
            </Section>

            <Section id="sg-controls" title="Controls" intro="One primary action per view. Every target is at least 44px tall. Focus is always visible.">
                <Controls />
            </Section>

            <Section id="sg-tags" title="Status" intro="Short, worded, never colour alone.">
                <div className={styles.tagRow}>
                    <Tag>ISA</Tag>
                    <Tag tone="accent">Risk 5 of 10</Tag>
                    <Tag tone="ok" icon={<CheckCircle weight="bold" />}>Within bands</Tag>
                    <Tag tone="warn" icon={<Warning weight="bold" />}>Rebalance due</Tag>
                    <Tag tone="loss">Price stale</Tag>
                </div>
            </Section>
        </article>
    )
}
