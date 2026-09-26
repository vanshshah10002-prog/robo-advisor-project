import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ChoiceGroup } from './ChoiceGroup'
import { MoneyField } from './MoneyField'
import { ErrorSummary, Notice } from './Notice'
import { Slider } from './Slider'

const OPTIONS = [
    { value: 1, label: 'Sell' },
    { value: 2, label: 'Hold' },
    { value: 3, label: 'Buy more' },
] as const

function Question({ numbered = true, error }: { numbered?: boolean; error?: string }) {
    const [value, setValue] = useState<number | null>(null)
    return <ChoiceGroup id="q-1" legend="Prices fall 20%" hint="Pick one" error={error} options={OPTIONS} value={value} onChange={setValue} numbered={numbered} />
}

describe('ChoiceGroup', () => {
    it('is a named group of radios, the first carrying the id an error links to', () => {
        render(<Question error="Choose an answer." />)
        const group = screen.getByRole('group', { name: 'Prices fall 20%' })
        const radios = within(group).getAllByRole('radio')
        expect(radios.map((r) => r.id)).toEqual(['q-1', '', ''])
        expect(group).toHaveAccessibleDescription('Pick one Choose an answer.')
    })

    it('picks an option with its number key and moves focus to it', async () => {
        const user = userEvent.setup()
        render(<Question />)
        await user.click(screen.getByRole('radio', { name: /Sell/ }))
        await user.keyboard('3')
        const buy = screen.getByRole('radio', { name: /Buy more/ })
        expect(buy).toBeChecked()
        expect(buy).toHaveFocus()
    })

    it('ignores numbers past the last option, with modifiers, or when not numbered', async () => {
        const user = userEvent.setup()
        const { unmount } = render(<Question />)
        await user.click(screen.getByRole('radio', { name: /Hold/ }))
        await user.keyboard('9')
        await user.keyboard('{Control>}1{/Control}')
        expect(screen.getByRole('radio', { name: /Hold/ })).toBeChecked()
        unmount()

        render(<Question numbered={false} />)
        await user.click(screen.getByRole('radio', { name: 'Hold' }))
        await user.keyboard('1')
        expect(screen.getByRole('radio', { name: 'Hold' })).toBeChecked()
    })
})

describe('Slider', () => {
    const stops = [1, 2, 3, 3.5]

    it('moves between stops and speaks each one', () => {
        const onChange = vi.fn()
        render(<Slider label="Risk level" hint="Lower only" stops={stops} value={3.5} onChange={onChange} format={String} describe={(v) => `Level ${v}`} />)
        const slider = screen.getByRole('slider', { name: 'Risk level' })
        expect(slider).toHaveAttribute('max', '3')
        expect(slider).toHaveAttribute('aria-valuetext', 'Level 3.5')
        expect(slider).toHaveAccessibleDescription('Lower only')
        fireEvent.change(slider, { target: { value: '1' } })
        expect(onChange).toHaveBeenCalledWith(2)
    })

    it('shows a value between stops at the nearest one, and speaks the format without a describe', () => {
        render(<Slider label="Risk level" stops={stops} value={2.2} onChange={() => {}} format={(v) => `L${v}`} />)
        expect(screen.getByRole('slider')).toHaveAttribute('aria-valuetext', 'L2')
    })

    it('is disabled with a single stop', () => {
        render(<Slider label="Risk level" stops={[1]} value={1} onChange={() => {}} format={String} />)
        expect(screen.getByRole('slider')).toBeDisabled()
    })
})

describe('Notice', () => {
    it('announces errors only', () => {
        const { rerender } = render(<Notice tone="error" title="Failed">Details</Notice>)
        expect(screen.getByRole('alert')).toHaveTextContent('FailedDetails')
        rerender(<Notice tone="warn" title="Careful" />)
        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
        rerender(<Notice title="Note" action={<button type="button">Fix</button>} />)
        expect(screen.getByRole('button', { name: 'Fix' })).toBeInTheDocument()
    })
})

describe('ErrorSummary', () => {
    it('renders nothing without errors', () => {
        const { container } = render(<ErrorSummary errors={[]} />)
        expect(container).toBeEmptyDOMElement()
    })

    it('takes focus when it appears and links to each field', async () => {
        const user = userEvent.setup()
        render(
            <>
                <ErrorSummary errors={[{ id: 'amount', message: 'Enter an amount.' }]} />
                <input id="amount" aria-label="Amount" />
            </>,
        )
        expect(screen.getByRole('alert')).toHaveFocus()
        expect(screen.getByText('Check these answers')).toBeInTheDocument()
        await user.click(screen.getByRole('link', { name: 'Enter an amount.' }))
        expect(screen.getByLabelText('Amount')).toHaveFocus()
    })
})

describe('MoneyField', () => {
    function Amount({ emptyValue, onChange }: { emptyValue?: number; onChange: (v: number | null) => void }) {
        return <MoneyField id="amount" label="Amount" value={50_000} emptyValue={emptyValue} onChange={onChange} />
    }

    it('starts from the value with separators, and reports what is typed as a number', async () => {
        const user = userEvent.setup()
        const onChange = vi.fn()
        render(<Amount onChange={onChange} />)
        const input = screen.getByLabelText('Amount')
        expect(input).toHaveValue('50,000')
        await user.clear(input)
        expect(onChange).toHaveBeenLastCalledWith(null)
        await user.type(input, '£1,250.5')
        expect(input).toHaveValue('£1,250.5')
        expect(onChange).toHaveBeenLastCalledWith(1_250.5)
        await user.type(input, 'x')
        expect(onChange).toHaveBeenLastCalledWith(null)
    })

    it('reports the empty value for a blank box when one is given', async () => {
        const user = userEvent.setup()
        const onChange = vi.fn()
        render(<Amount emptyValue={0} onChange={onChange} />)
        await user.clear(screen.getByLabelText('Amount'))
        expect(onChange).toHaveBeenLastCalledWith(0)
    })
})
