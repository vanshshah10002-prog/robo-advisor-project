import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AllocationBar } from './AllocationBar'
import { ChartFrame } from './ChartFrame'
import { DriftBars } from './DriftBars'
import { FanChart, type FanData } from './FanChart'
import { Legend } from './Legend'
import { LineChart } from './LineChart'
import type { AllocationItem, DriftItem } from './model'

/** The polite live region a chart uses to announce keyboard moves. */
const announced = (container: HTMLElement) => container.querySelector('[aria-live="polite"]')?.textContent ?? ''

const focus = (el: HTMLElement) => act(() => el.focus())

describe('ChartFrame', () => {
    const frame = (props: Partial<Parameters<typeof ChartFrame>[0]> = {}) =>
        render(
            <ChartFrame title="Value" table={<table aria-label="twin" />} notes="Source: prices" {...props}>
                <svg data-testid="plot" />
            </ChartFrame>,
        )

    it('names the figure by its title and shows the chart first', () => {
        frame({ provenance: 'measured', summary: 'Up 4%.' })
        expect(screen.getByRole('figure', { name: 'Value' })).toBeInTheDocument()
        expect(screen.getByTestId('plot')).toBeInTheDocument()
        expect(screen.getByText('Up 4%.')).toBeInTheDocument()
        expect(screen.getByText('measured')).toBeInTheDocument()
        expect(screen.getByText('Source: prices')).toBeInTheDocument()
    })

    it('switches to the table twin and back, marking the pressed view', async () => {
        const user = userEvent.setup()
        frame()
        const table = screen.getByRole('button', { name: 'Table' })
        await user.click(table)
        expect(table).toHaveAttribute('aria-pressed', 'true')
        expect(screen.getByRole('table', { name: 'twin' })).toBeInTheDocument()
        expect(screen.queryByTestId('plot')).not.toBeInTheDocument()

        await user.click(screen.getByRole('button', { name: 'Chart' }))
        expect(screen.getByTestId('plot')).toBeInTheDocument()
    })

    it('keeps the last render on screen, marked busy, while refetching', () => {
        frame({ pending: true })
        expect(screen.getByRole('figure')).toHaveAttribute('aria-busy', 'true')
        expect(screen.getByTestId('plot')).toBeInTheDocument()
    })

    it('replaces chart and switch with a message when empty', () => {
        frame({ empty: 'No history yet.' })
        expect(screen.getByText('No history yet.')).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Table' })).not.toBeInTheDocument()
        expect(screen.queryByTestId('plot')).not.toBeInTheDocument()
    })
})

describe('Legend', () => {
    it('lists each series with a key drawn like its mark', () => {
        const { container } = render(
            <Legend
                items={[
                    { key: 'a', label: 'Strategy', colour: '#2f59ab', mark: 'line' },
                    { key: 'b', label: 'Paid in', colour: '#69625a', mark: 'dash' },
                    { key: 'c', label: 'Middle half', colour: 'rgb(0 0 0 / 0.2)', mark: 'band' },
                    { key: 'd', label: 'Growth', colour: '#00574c' },
                ]}
            />,
        )
        expect(screen.getAllByRole('listitem')).toHaveLength(4)
        expect(container.querySelector('line[stroke-dasharray]')).not.toBeNull()
        expect(container.querySelectorAll('rect')).toHaveLength(2)
    })

    it('draws its keys through style, where a token reference resolves', () => {
        const { container } = render(
            <Legend
                items={[
                    { key: 'a', label: 'Strategy', colour: 'var(--chart-cat-1)', mark: 'line' },
                    { key: 'b', label: 'Growth', colour: 'var(--chart-growth-1)' },
                ]}
            />,
        )
        expect(container.querySelector('line')?.getAttribute('style')).toContain('stroke: var(--chart-cat-1)')
        expect(container.querySelector('rect')?.getAttribute('style')).toContain('fill: var(--chart-growth-1)')
        expect(container.querySelector('[fill^="var("], [stroke^="var("]')).toBeNull()
    })
})

const holdings: AllocationItem[] = [
    { key: 'VAGP.L', label: 'Global bonds', detail: 'VAGP.L', sleeve: 'defensive', weight: 0.3, value: 30_000 },
    { key: 'VWRL.L', label: 'Global equity', detail: 'VWRL.L', sleeve: 'growth', weight: 0.5, value: 50_000 },
    { key: 'ERNS.L', label: 'Cash-like', sleeve: 'defensive', weight: 0.2, value: 20_000 },
]

describe('AllocationBar', () => {
    it('summarises the sleeve split and lists holdings growth first', () => {
        render(<AllocationBar title="Holdings" items={holdings} />)
        expect(screen.getByRole('img', { name: /Holdings: growth 50%, defensive 50%, across 3 holdings/ })).toBeInTheDocument()
        const names = screen.getAllByRole('listitem').map((li) => li.textContent)
        expect(names[0]).toContain('Global equity')
        expect(names[2]).toContain('Cash-like')
    })

    it('leaves out the sleeve split when every holding is in one sleeve', () => {
        const regions: AllocationItem[] = [
            { key: 'us', label: 'US shares', sleeve: 'growth', weight: 0.7 },
            { key: 'uk', label: 'UK shares', sleeve: 'growth', weight: 0.3 },
        ]
        render(<AllocationBar title="Where the shares are" items={regions} />)
        expect(screen.getByRole('img', { name: /^Where the shares are: across 2 holdings\./ })).toBeInTheDocument()
        expect(screen.queryByText('Growth')).not.toBeInTheDocument()
    })

    it('reads holdings from the keyboard: latest on focus, Home to the first', async () => {
        const user = userEvent.setup()
        const { container } = render(<AllocationBar title="Holdings" items={holdings} />)
        const strip = screen.getByRole('img')
        await focus(strip)
        expect(announced(container)).toContain('Cash-like')
        await user.keyboard('{Home}')
        expect(announced(container)).toBe('Global equity. Share 50.0%. Value £50,000. Sleeve Growth')
        await user.keyboard('{Escape}')
        expect(announced(container)).toBe('')
    })

    it('shows the segment under the pointer and hides it on leave', () => {
        render(<AllocationBar title="Holdings" items={holdings} />)
        const strip = screen.getByRole('img')
        fireEvent.pointerMove(strip, { clientX: 400 })
        expect(screen.getByText('Global bonds · VAGP.L')).toBeInTheDocument()
        fireEvent.pointerLeave(strip)
        expect(screen.queryByText('Global bonds · VAGP.L')).not.toBeInTheDocument()
    })

    it('has a table twin with a 100% total', async () => {
        const user = userEvent.setup()
        render(<AllocationBar title="Holdings" items={holdings} />)
        await user.click(screen.getByRole('button', { name: 'Table' }))
        const table = screen.getByRole('table', { name: 'Holdings' })
        expect(within(table).getAllByRole('row')).toHaveLength(5)
        expect(within(table).getByText('100%')).toBeInTheDocument()
        expect(within(table).getByText('£100,000')).toBeInTheDocument()
    })

    it('leaves out the value column when no values are known', async () => {
        const user = userEvent.setup()
        render(<AllocationBar title="Proposal" items={holdings.map(({ value: _v, ...h }) => h)} />)
        await user.click(screen.getByRole('button', { name: 'Table' }))
        expect(screen.queryByRole('columnheader', { name: 'Value' })).not.toBeInTheDocument()
    })

    it('says so when there is nothing to show', () => {
        render(<AllocationBar title="Holdings" items={[]} />)
        expect(screen.getByText('Nothing to show yet.')).toBeInTheDocument()
    })
})

const fan: FanData = {
    years: [0, 1, 2, 3],
    p10: [100, 95, 97, 101],
    p25: [100, 101, 104, 108],
    p50: [100, 105, 110, 116],
    p75: [100, 109, 117, 125],
    p90: [100, 115, 126, 138],
    paidIn: [100, 100, 100, 100],
}

describe('FanChart', () => {
    it('describes the final spread in its accessible name', () => {
        render(<FanChart title="Projection" data={fan} goal={120} />)
        expect(
            screen.getByRole('img', { name: /By 3 yrs the middle outcome is £116; 1 in 10 outcomes end below £101 and 1 in 10 above £138/ }),
        ).toBeInTheDocument()
        expect(screen.getByText('Goal £120')).toBeInTheDocument()
        expect(screen.getByText('simulated')).toBeInTheDocument()
    })

    it('steps through years with the keyboard, announcing every series', async () => {
        const user = userEvent.setup()
        const { container } = render(<FanChart title="Projection" data={fan} startYear={2026} />)
        await focus(screen.getByRole('img'))
        expect(announced(container)).toBe(
            '2029, year 3. Best 1 in 10 above £138. Best 1 in 4 above £125. Middle outcome £116. ' +
                'Worst 1 in 4 below £108. Worst 1 in 10 below £101. Paid in £100',
        )
        await user.keyboard('{ArrowLeft}')
        expect(announced(container)).toMatch(/^2028, year 2\./)
        await user.keyboard('{PageDown}{PageDown}')
        expect(announced(container)).toMatch(/^2026, now\./)
        await user.keyboard('{ArrowDown}')
        expect(announced(container)).toMatch(/^2026, now\./)
        await user.keyboard('{End}')
        expect(announced(container)).toMatch(/^2029/)
        await user.keyboard('{ArrowRight}')
        expect(announced(container)).toMatch(/^2029/)
    })

    it('follows the pointer and forgets it on leave', () => {
        const { container } = render(<FanChart title="Projection" data={fan} />)
        const hit = container.querySelector('rect[class*="hit"]') as SVGRectElement
        fireEvent.pointerMove(hit, { clientX: 5_000 })
        expect(screen.getByText('Year 3')).toBeInTheDocument()
        fireEvent.pointerMove(hit, { clientX: 180 })
        expect(screen.getByText('Year 1')).toBeInTheDocument()
        expect(announced(container)).toBe('')
        fireEvent.pointerLeave(hit)
        expect(screen.queryByText('Year 1')).not.toBeInTheDocument()
    })

    it('has one table row per year', async () => {
        const user = userEvent.setup()
        render(<FanChart title="Projection" data={fan} />)
        await user.click(screen.getByRole('button', { name: 'Table' }))
        const table = screen.getByRole('table', { name: 'Projection' })
        expect(within(table).getAllByRole('row')).toHaveLength(5)
        expect(within(table).getByRole('rowheader', { name: 'Year 2' })).toBeInTheDocument()
        expect(within(table).getByRole('columnheader', { name: 'Paid in' })).toBeInTheDocument()
    })

    it('needs at least two years to draw', () => {
        const one = { years: [0], p10: [1], p25: [1], p50: [1], p75: [1], p90: [1] }
        render(<FanChart title="Projection" data={one} />)
        expect(screen.getByText('Not enough years to draw a projection.')).toBeInTheDocument()
    })
})

const dates = ['2024-01-05', '2024-01-12', '2024-01-19']

describe('LineChart', () => {
    const series = [
        { key: 's', label: 'Strategy', colour: '#2f59ab', values: [100, 104, null], variant: 'area' as const },
        { key: 'b', label: 'Benchmark', colour: '#008b77', values: [100, 102, 103] },
        { key: 'p', label: 'Paid in', colour: '#69625a', values: [100, 100, 100], variant: 'reference' as const },
    ]

    it('draws a legend for several series and a labelled baseline', () => {
        const { container } = render(
            <LineChart title="Growth" dates={dates} series={series} format={String} baseline={{ value: 100, label: 'Invested' }} />,
        )
        expect(screen.getAllByRole('listitem')).toHaveLength(3)
        expect(screen.getByText('Invested')).toBeInTheDocument()
        expect(container.querySelector('path[fill-opacity]')).not.toBeNull()
        expect(container.querySelector('path[stroke-dasharray]')).not.toBeNull()
    })

    it('omits the legend for a single series', () => {
        render(<LineChart title="Growth" dates={dates} series={[series[1]]} format={String} />)
        expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
    })

    it('reads every series at the cursor, with a dash for a gap', async () => {
        const { container } = render(<LineChart title="Growth" dates={dates} series={series} format={(v) => `£${v}`} />)
        await focus(screen.getByRole('img'))
        expect(announced(container)).toBe('19 Jan 2024. Strategy —. Benchmark £103. Paid in £100')
    })

    it('follows the pointer across dates', () => {
        const { container } = render(<LineChart title="Growth" dates={dates} series={series} format={String} />)
        const hit = container.querySelector('rect[class*="hit"]') as SVGRectElement
        fireEvent.pointerMove(hit, { clientX: 290 })
        expect(screen.getByText('12 Jan 2024')).toBeInTheDocument()
        fireEvent.pointerLeave(hit)
        expect(screen.queryByText('12 Jan 2024')).not.toBeInTheDocument()
    })

    it('samples long series in the table twin', async () => {
        const user = userEvent.setup()
        const many = Array.from({ length: 100 }, (_, i) => new Date(Date.UTC(2024, 0, 1 + i)).toISOString().slice(0, 10))
        render(
            <LineChart
                title="Growth"
                dates={many}
                series={[{ key: 'v', label: 'Value', colour: '#2f59ab', values: many.map((_, i) => i) }]}
                format={String}
                tableRows={10}
            />,
        )
        await user.click(screen.getByRole('button', { name: 'Table' }))
        const rows = within(screen.getByRole('table')).getAllByRole('row')
        expect(rows.length).toBeLessThanOrEqual(11)
        expect(rows.at(-1)).toHaveTextContent('9 Apr 2024')
    })

    it('shows the empty message with fewer than two dates', () => {
        render(<LineChart title="Growth" dates={['2024-01-05']} series={[]} format={String} empty="Opened today." />)
        expect(screen.getByText('Opened today.')).toBeInTheDocument()
    })
})

const drifting: DriftItem[] = [
    { key: 'VWRL.L', label: 'Global equity', detail: 'VWRL.L', target: 0.5, current: 0.54, band: 0.025 },
    { key: 'VAGP.L', label: 'Global bonds', target: 0.3, current: 0.29, band: 0.025 },
    { key: 'ERNS.L', label: 'Cash-like', target: 0.2, current: null, band: 0.025 },
]

describe('DriftBars', () => {
    it('flags a holding outside its band in words, not only colour', () => {
        render(<DriftBars title="Drift" items={drifting} />)
        expect(screen.getByRole('list', { name: 'Drift: 1 outside its band' })).toBeInTheDocument()
        expect(screen.getAllByText('Outside band')).toHaveLength(1)
        expect(screen.getByText('+4.0 pp')).toBeInTheDocument()
        expect(screen.getByText('no price')).toBeInTheDocument()
    })

    it('says when everything is within its band', () => {
        render(<DriftBars title="Drift" items={[drifting[1]]} />)
        expect(screen.getByRole('list', { name: 'Drift: every holding is within its band' })).toBeInTheDocument()
    })

    it('has a table twin with a status for every holding', async () => {
        const user = userEvent.setup()
        render(<DriftBars title="Drift" items={drifting} />)
        await user.click(screen.getByRole('button', { name: 'Table' }))
        const table = screen.getByRole('table', { name: 'Drift' })
        expect(within(table).getByText('Outside band')).toBeInTheDocument()
        expect(within(table).getByText('Within band')).toBeInTheDocument()
        expect(within(table).getByText('No price')).toBeInTheDocument()
        expect(within(table).getAllByText('±2.5 pp')).toHaveLength(3)
    })

    it('says so with no holdings', () => {
        render(<DriftBars title="Drift" items={[]} />)
        expect(screen.getByText('No holdings to compare yet.')).toBeInTheDocument()
    })
})

describe('a live cursor when a refetch shortens the data', () => {
    it('fan chart: moves to the new last year instead of reading past the end', async () => {
        const { container, rerender } = render(<FanChart title="Projection" data={fan} startYear={2026} />)
        await focus(screen.getByRole('img'))
        expect(announced(container)).toMatch(/^2029, year 3\./)

        const shorter: FanData = {
            years: [0, 1],
            p10: [100, 95],
            p25: [100, 101],
            p50: [100, 105],
            p75: [100, 109],
            p90: [100, 115],
        }
        rerender(<FanChart title="Projection" data={shorter} startYear={2026} />)
        expect(announced(container)).toBe(
            '2027, year 1. Best 1 in 10 above £115. Best 1 in 4 above £109. Middle outcome £105. Worst 1 in 4 below £101. Worst 1 in 10 below £95',
        )
        expect(container.innerHTML).not.toMatch(/NaN|undefined/)
    })

    it('line chart: keeps the crosshair on real data', async () => {
        const one = [{ key: 'b', label: 'Benchmark', colour: '#008b77', values: [100, 102, 103] }]
        const { container, rerender } = render(<LineChart title="Growth" dates={dates} series={one} format={String} />)
        await focus(screen.getByRole('img'))
        rerender(<LineChart title="Growth" dates={dates.slice(0, 2)} series={[{ ...one[0], values: [100, 102] }]} format={String} />)
        expect(announced(container)).toBe('12 Jan 2024. Benchmark 102')
        expect(container.innerHTML).not.toMatch(/NaN/)
    })

    it('allocation strip: still highlights a real segment', async () => {
        const { container, rerender } = render(<AllocationBar title="Holdings" items={holdings} />)
        await focus(screen.getByRole('img'))
        rerender(<AllocationBar title="Holdings" items={holdings.slice(0, 2)} />)
        expect(announced(container)).toMatch(/^Global bonds\./)
        expect(container.querySelectorAll('[class*="dim"]')).toHaveLength(1)
    })
})
