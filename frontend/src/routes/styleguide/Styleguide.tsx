import { ArrowRight, CheckCircle, Warning } from '@phosphor-icons/react'
import { useMemo, useState, type ReactNode } from 'react'
import { AllocationBar, DataTable, DriftBars, FanChart, FundCell, LineChart, type Column } from '@/charts'
import { contrast } from '@/lib/contrast'
import { money, moneyCompact, percent, signedPercent } from '@/lib/format'
import { CATEGORICAL } from '@/lib/palette'
import { usePageTheme } from '@/lib/theme'
import { usePageTitle } from '@/lib/usePageTitle'
import { Button } from '@/ui/Button'
import { Field, TextInput } from '@/ui/Field'
import { Delta, Stat, StatGroup } from '@/ui/Stat'
import { Provenance, Tag } from '@/ui/Tag'
import { Term } from '@/ui/Term'
import {
    SPECIMEN_BAND,
    SPECIMEN_DRIFT,
    SPECIMEN_HOLDINGS,
    SPECIMEN_TOTAL,
    specimenFan,
    specimenTrack,
    type SpecimenHolding,
} from './specimen'
import styles from './Styleguide.module.css'

const SWATCHES = [
    { group: 'Surfaces', items: [['Paper', 'color-paper'], ['Sheet', 'color-sheet'], ['Sunk', 'color-sunk']] },
    { group: 'Ink', items: [['Ink', 'color-ink'], ['Ink 2', 'color-ink-2'], ['Ink 3', 'color-ink-3']] },
    { group: 'Rules', items: [['Hairline', 'color-rule'], ['Control edge', 'color-rule-strong']] },
    { group: 'Meaning', items: [['Action', 'color-accent'], ['Loss', 'color-loss'], ['OK', 'color-ok'], ['Caution', 'color-warn']] },
] as const

const steps = (name: string, count: number) => Array.from({ length: count }, (_, i) => `chart-${name}-${i + 1}`)

const RAMPS = [
    { name: 'Growth', tokens: steps('growth', 5) },
    { name: 'Defensive', tokens: steps('defensive', 5) },
    { name: 'Comparison (fixed order)', tokens: steps('cat', 6) },
] as const

const HEX = /^#[0-9a-f]{6}$/i

/**
 * The value each colour token has on the page right now, read back from the
 * browser so this page shows the theme in effect, not a copy of it.
 */
function useTokenValues(): { theme: string; value: (token: string) => string } {
    const theme = usePageTheme()
    const style = getComputedStyle(document.documentElement)
    return { theme, value: (token) => style.getPropertyValue(`--${token}`).trim().toLowerCase() }
}

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

function Swatch({ name, token, value, paper }: { name: string; token: string; value: string; paper: string }) {
    const ratio = HEX.test(value) && HEX.test(paper) ? contrast(value, paper) : null
    return (
        <li className={styles.swatch}>
            <span className={styles.chip} style={{ background: `var(--${token})` }} />
            <span className={styles.swatchName}>{name}</span>
            <code className={styles.swatchMeta}>--{token}</code>
            <span className={styles.swatchMeta}>
                {value}
                {ratio !== null && ` · ${ratio.toFixed(1)}:1 ${grade(ratio)}`}
            </span>
        </li>
    )
}

function Swatches() {
    const { theme, value } = useTokenValues()
    return (
        <div className={styles.swatchGroups}>
            <p className={styles.swatchNote}>Values and contrast on paper for the {theme} theme, read from the page as it is now.</p>
            {SWATCHES.map(({ group, items }) => (
                <div key={group}>
                    <h3 className="label">{group}</h3>
                    <ul className={styles.swatches}>
                        {items.map(([name, token]) => (
                            <Swatch key={token} name={name} token={token} value={value(token)} paper={value('color-paper')} />
                        ))}
                    </ul>
                </div>
            ))}
        </div>
    )
}

function Ramps() {
    const { value } = useTokenValues()
    return (
        <div className={styles.ramps}>
            {RAMPS.map(({ name, tokens }) => (
                <div key={name} className={styles.ramp}>
                    <span className="label">{name}</span>
                    <div className={styles.rampSteps}>
                        {tokens.map((token, i) => (
                            <span key={token} style={{ background: `var(--${token})` }} title={value(token)}>
                                <span className="visually-hidden">
                                    Step {i + 1}: {value(token)}
                                </span>
                            </span>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    )
}

const HOLDING_COLUMNS: Column<SpecimenHolding>[] = [
    { key: 'fund', label: 'Fund', render: (h) => <FundCell name={h.name} ticker={h.ticker} /> },
    { key: 'sleeve', label: 'Sleeve', render: (h) => (h.sleeve === 'growth' ? 'Growth' : 'Defensive') },
    { key: 'value', label: 'Value', numeric: true, render: (h) => money(h.value) },
    { key: 'weight', label: 'Weight', numeric: true, render: (h) => percent(h.weight, 0) },
    { key: 'return', label: 'Return', numeric: true, render: (h) => <Delta value={h.returnPct} /> },
]

function StatementTable() {
    return (
        <figure className={styles.figure}>
            <figcaption className={styles.figcaption}>
                <span>Holdings</span>
                <span className="label">Illustrative figures</span>
            </figcaption>
            <DataTable
                caption="Holdings, illustrative"
                stack
                columns={HOLDING_COLUMNS}
                rows={SPECIMEN_HOLDINGS}
                rowKey={(h) => h.ticker}
                footer={['Total', '', money(SPECIMEN_TOTAL), percent(1, 0), <Delta key="total" value={0.245} />]}
            />
        </figure>
    )
}

const ALLOCATION = SPECIMEN_HOLDINGS.map((h) => ({ key: h.ticker, label: h.label, detail: h.ticker, sleeve: h.sleeve, weight: h.weight, value: h.value }))

const DRIFT = SPECIMEN_HOLDINGS.map((h, i) => ({
    key: h.ticker,
    label: h.label,
    detail: h.ticker,
    target: h.weight,
    current: h.weight + SPECIMEN_DRIFT[i],
    band: SPECIMEN_BAND,
}))

function Charts() {
    const fan = useMemo(() => specimenFan(), [])
    const track = useMemo(() => specimenTrack(), [])
    return (
        <div className={styles.charts}>
            <AllocationBar
                title="What the portfolio holds"
                summary="Seven funds: half in growth, half in defensive holdings."
                provenance="measured"
                items={ALLOCATION}
            />
            <FanChart
                title="Your money, fifteen years on"
                summary="£50,000 now and £250 a month. The shaded bands are the 50% and 80% probability ranges of the simulated outcomes."
                data={fan}
                goal={150_000}
                startYear={2026}
                notes="Illustrative: lognormal returns of 5.5% a year with 11% volatility, before fees and inflation."
            />
            <LineChart
                title="£10,000 over five years"
                summary="The strategy against a benchmark of 50% VWRL.L and 50% AGBP.L, rebalanced the same way."
                provenance="measured"
                dates={track.dates}
                series={[
                    { key: 'strategy', label: 'This strategy', colour: CATEGORICAL[0], values: track.strategy },
                    { key: 'benchmark', label: 'Benchmark: 50% VWRL.L + 50% AGBP.L', colour: CATEGORICAL[1], values: track.benchmark },
                ]}
                baseline={{ value: 10_000, label: '£10,000 invested' }}
                format={(v) => money(v)}
                axisFormat={moneyCompact}
                notes="Illustrative series from a seeded random walk; the real walk-forward record arrives with the workspace."
            />
            <DriftBars
                title="Distance from target"
                summary="Each holding against its target weight. One has drifted outside its band, so a rebalance is due."
                items={DRIFT}
                notes="Band: 2.5 percentage points either side of target."
            />
        </div>
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
    usePageTitle('Style guide')
    const theme = usePageTheme()
    return (
        <article className={styles.page}>
            <header className={styles.masthead}>
                <div className={styles.dateline}>
                    <span className="label">Design system</span>
                    <span className="label">{theme === 'dark' ? 'Dark' : 'Light'} theme · September 2026</span>
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
                <Ramps />
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

            <Section id="sg-charts" title="Charts" intro="Every chart has a table twin, a legend when it has two series, and a readout that follows the pointer or the arrow keys. Data here is illustrative.">
                <Charts />
            </Section>

            <Section id="sg-figures" title="Figures" intro="Tabular numerals, right-aligned, signed. Totals sit under a double rule, as on paper.">
                <StatementTable />
            </Section>

            <Section id="sg-stats" title="Headline figures" intro="The one number that matters is large; everything else steps down. A technical term is underlined with dots: hover, tap or tab to it for its meaning. Figures here are illustrative.">
                <StatGroup className={styles.stats}>
                    <Stat size="lg" label="Portfolio value" provenance="measured" value={money(SPECIMEN_TOTAL)} detail={<><Delta value={0.245} /> since you started</>} />
                    <Stat label={<>In 15 years, <Term explain="median">median</Term></>} provenance="simulated" value={money(238_400)} detail="80% probability between £161k and £352k" />
                    <Stat label={<Term explain="expectedReturn">Expected return</Term>} provenance="estimated" value={percent(0.048)} detail="a year, before inflation" />
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
