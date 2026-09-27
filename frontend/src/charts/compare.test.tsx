import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CompareBars } from './CompareBars'
import { DataTable, type Column } from './DataTable'
import { Heatmap } from './Heatmap'
import type { CompareItem, MatrixLabel } from './model'
import { Sparkline } from './Sparkline'

const labels: MatrixLabel[] = [
    { key: 'VUAG.L', label: 'US shares', short: 'VUAG.L' },
    { key: 'ISF.L', label: 'UK shares', short: 'ISF.L' },
    { key: 'ERNS.L', label: 'Cash-like fund', short: 'ERNS.L' },
]
const matrix = [
    [1, 0.78, -0.05],
    [0.78, 1, 0.1],
    [-0.05, 0.1, 1],
]

describe('Heatmap', () => {
    it('names the closest and the most independent pair for a screen reader', () => {
        render(<Heatmap title="How the funds move together" labels={labels} matrix={matrix} />)
        expect(
            screen.getByRole('img', {
                name: 'Correlations between 3 funds. Closest: US shares and UK shares, 0.78. Most independent: US shares and Cash-like fund, −0.05.',
            }),
        ).toBeInTheDocument()
    })

    it('prints every figure off the diagonal, with a true minus sign', () => {
        render(<Heatmap title="Correlations" labels={labels} matrix={matrix} />)
        const grid = screen.getByRole('img')
        expect(within(grid).getAllByText('0.78')).toHaveLength(2)
        expect(within(grid).getAllByText('−0.05')).toHaveLength(2)
        expect(within(grid).queryByText('1.00')).not.toBeInTheDocument()
    })

    it('has a table twin with a dash where a fund meets itself', async () => {
        const user = userEvent.setup()
        render(<Heatmap title="Correlations" labels={labels} matrix={matrix} />)
        await user.click(screen.getByRole('button', { name: 'Table' }))
        const rows = within(screen.getByRole('table', { name: 'Correlations' })).getAllByRole('row')
        expect(rows).toHaveLength(4)
        expect(rows[1]).toHaveTextContent(/US shares.*VUAG\.L.*—.*0\.78.*−0\.05/)
    })

    it('needs two funds to compare', () => {
        render(<Heatmap title="Correlations" labels={labels.slice(0, 1)} matrix={[[1]]} />)
        expect(screen.getByText('Correlations need at least two funds.')).toBeInTheDocument()
    })
})

describe('CompareBars', () => {
    const items: CompareItem[] = [
        { key: 'us', label: 'US shares', detail: 'VUAG.L', values: [0.45, 0.71] },
        { key: 'cash', label: 'Cash-like fund', detail: 'ERNS.L', values: [0.15, 0.001] },
    ]
    const series = [
        { label: 'Share of the money', colour: '#777' },
        { label: 'Share of the risk', colour: '#246' },
    ] as const

    it('draws both measures on one scale, each bar carrying its figure', () => {
        render(<CompareBars title="Money and risk" items={items} series={series} />)
        const list = screen.getByRole('list', { name: 'Money and risk' })
        const [us] = within(list).getAllByRole('listitem')
        expect(us).toHaveTextContent('Share of the money: 45.0%')
        expect(us).toHaveTextContent('Share of the risk: 71.0%')
        const fills = us.querySelectorAll<HTMLElement>('[style*="width"]')
        expect(fills[1].style.width).toBe('100%')
        expect(Number.parseFloat(fills[0].style.width)).toBeCloseTo((0.45 / 0.71) * 100, 5)
    })

    it('shows a legend and a table twin with both measures', async () => {
        const user = userEvent.setup()
        render(<CompareBars title="Money and risk" items={items} series={series} format={(v) => `${Math.round(v * 100)}%`} />)
        expect(screen.getAllByText('Share of the risk').length).toBeGreaterThan(0)
        await user.click(screen.getByRole('button', { name: 'Table' }))
        const table = screen.getByRole('table', { name: 'Money and risk' })
        expect(within(table).getAllByRole('row')[2]).toHaveTextContent(/Cash-like fund.*15%.*0%/)
    })

    it('draws no bar for a share below zero, but still prints it', () => {
        const hedge: CompareItem[] = [{ key: 'gold', label: 'Gold', values: [0.05, -0.02] }]
        render(<CompareBars title="Money and risk" items={hedge} series={series} />)
        const gold = within(screen.getByRole('list', { name: 'Money and risk' })).getByRole('listitem')
        expect(gold.querySelectorAll<HTMLElement>('[style*="width"]')[1].style.width).toBe('0%')
        expect(gold).toHaveTextContent('Share of the risk: −2.0%')
    })

    it('says so when there is nothing to compare', () => {
        render(<CompareBars title="Money and risk" items={[]} series={series} />)
        expect(screen.getByText('Nothing to compare yet.')).toBeInTheDocument()
    })
})

describe('Sparkline', () => {
    it('draws a labelled line through every value, ending on a dot', () => {
        const { container } = render(<Sparkline values={[100, 90, 120]} label="Value from £100 to £120" width={100} height={20} />)
        expect(screen.getByRole('img', { name: 'Value from £100 to £120' })).toBeInTheDocument()
        expect(container.querySelector('polyline')?.getAttribute('points')).toBe('2.0,12.7 50.0,18.0 98.0,2.0')
        expect(container.querySelector('circle')).toHaveAttribute('cx', '98')
    })

    it('draws a flat line through the middle when nothing changes', () => {
        const { container } = render(<Sparkline values={[5, 5]} label="Flat" width={100} height={20} />)
        expect(container.querySelector('polyline')?.getAttribute('points')).toBe('2.0,10.0 98.0,10.0')
    })

    it('draws nothing from fewer than two values', () => {
        const { container } = render(<Sparkline values={[5]} label="One" />)
        expect(container).toBeEmptyDOMElement()
    })
})

describe('DataTable', () => {
    type Row = { name: string; value: number }
    const columns: Column<Row>[] = [
        { key: 'name', label: 'Fund', render: (r) => r.name },
        { key: 'value', label: 'Value', numeric: true, render: (r) => `£${r.value}` },
        { key: 'note', label: <abbr title="Total expense ratio">TER</abbr>, stackLabel: 'Yearly fee', render: () => '0.1%' },
    ]
    const rows = [{ name: 'VUAG.L', value: 10 }]

    it('labels each stacked cell for phones and keeps the table roles', () => {
        render(<DataTable caption="Funds" columns={columns} rows={rows} rowKey={(r) => r.name} footer={['Total', '£10', '']} stack />)
        const table = screen.getByRole('table', { name: 'Funds' })
        expect(table).toHaveAttribute('role', 'table')
        expect(within(table).getByRole('rowheader', { name: 'VUAG.L' })).toBeInTheDocument()
        const cells = within(table).getAllByRole('cell')
        expect(cells.map((c) => c.getAttribute('data-label'))).toEqual(['Value', 'Yearly fee', 'Value', 'Yearly fee'])
        expect(cells[3]).toBeEmptyDOMElement()
        // Each value is one box beside its label, so a fund's name and ticker stay together.
        expect(cells[0].children).toHaveLength(1)
        expect(cells[0].firstElementChild).toHaveTextContent('£10')
    })

    it('leaves the native roles alone when not stacked', () => {
        render(<DataTable caption="Funds" columns={columns} rows={rows} rowKey={(r) => r.name} />)
        expect(screen.getByRole('table', { name: 'Funds' })).not.toHaveAttribute('role')
        expect(screen.getAllByRole('cell')[0].children).toHaveLength(0)
    })

    it('can be reached by keyboard and named when it scrolls sideways, and only then', () => {
        let wide = true
        vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(() => (wide ? 900 : 400))
        vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(400)
        let resized = () => {}
        vi.stubGlobal('ResizeObserver', class {
            constructor(callback: () => void) {
                resized = callback
            }
            observe() {}
            disconnect() {}
        })

        render(<DataTable caption="Funds" columns={columns} rows={rows} rowKey={(r) => r.name} />)
        const region = screen.getByRole('region', { name: 'Funds' })
        expect(region).toHaveAttribute('tabindex', '0')
        expect(region).toContainElement(screen.getByRole('table'))

        wide = false
        act(() => resized())
        expect(screen.queryByRole('region')).not.toBeInTheDocument()
        expect(screen.getByRole('table').parentElement).not.toHaveAttribute('tabindex')
        vi.restoreAllMocks()
    })

    it('adds no stop for the keyboard where the browser cannot measure', () => {
        vi.stubGlobal('ResizeObserver', undefined)
        render(<DataTable caption="Funds" columns={columns} rows={rows} rowKey={(r) => r.name} />)
        expect(screen.queryByRole('region')).not.toBeInTheDocument()
    })
})
