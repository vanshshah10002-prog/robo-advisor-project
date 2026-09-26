import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { Button, ButtonLink } from './Button'
import { ErrorBoundary } from './ErrorBoundary'
import { Field, TextInput } from './Field'
import { Delta, Stat, StatGroup } from './Stat'
import { PROVENANCE_MEANING } from './provenance'
import { Provenance, Tag } from './Tag'

describe('Button', () => {
    it('calls onClick', async () => {
        const onClick = vi.fn()
        render(<Button onClick={onClick}>Continue</Button>)
        await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
        expect(onClick).toHaveBeenCalledOnce()
    })

    it('defaults to type="button" so it never submits a form by accident', () => {
        render(<Button>Save</Button>)
        expect(screen.getByRole('button')).toHaveAttribute('type', 'button')
    })

    it('announces loading and ignores clicks while busy', async () => {
        const onClick = vi.fn()
        render(
            <Button loading onClick={onClick}>
                Build portfolio
            </Button>,
        )
        const button = screen.getByRole('button', { name: 'Build portfolio' })
        expect(button).toHaveAttribute('aria-busy', 'true')
        expect(button).toHaveAttribute('aria-disabled', 'true')
        await userEvent.click(button)
        expect(onClick).not.toHaveBeenCalled()
    })

    it('hides decorative icons from assistive tech', () => {
        render(<Button trailingIcon={<svg data-testid="icon" />}>Next</Button>)
        expect(screen.getByTestId('icon').parentElement).toHaveAttribute('aria-hidden', 'true')
    })

    it('renders ButtonLink as a real link', () => {
        render(
            <MemoryRouter>
                <ButtonLink to="/start" variant="secondary">
                    Start
                </ButtonLink>
            </MemoryRouter>,
        )
        expect(screen.getByRole('link', { name: 'Start' })).toHaveAttribute('href', '/start')
    })
})

describe('Field', () => {
    it('ties the label to the control', () => {
        render(<Field label="Amount to invest (£)">{(c) => <TextInput {...c} prefix="£" />}</Field>)
        expect(screen.getByLabelText('Amount to invest (£)')).toBeInstanceOf(HTMLInputElement)
    })

    it('describes the control with its hint and error, and marks it invalid', () => {
        render(
            <Field label="Monthly amount" hint="You can change this later." error="Enter £0 or more.">
                {(c) => <TextInput {...c} />}
            </Field>,
        )
        const input = screen.getByLabelText('Monthly amount')
        expect(input).toHaveAccessibleDescription('You can change this later. Enter £0 or more.')
        expect(input).toHaveAttribute('aria-invalid', 'true')
    })

    it('leaves a valid control undescribed and not invalid', () => {
        render(<Field label="Name">{(c) => <TextInput {...c} />}</Field>)
        const input = screen.getByLabelText('Name')
        expect(input).not.toHaveAttribute('aria-describedby')
        expect(input).not.toHaveAttribute('aria-invalid')
    })

    it('marks optional fields in words', () => {
        render(
            <Field label="Email" optional>
                {(c) => <TextInput {...c} />}
            </Field>,
        )
        expect(screen.getByText('(optional)')).toBeInTheDocument()
    })
})

describe('Stat and Delta', () => {
    it('renders a term and its value inside a description list', () => {
        render(
            <StatGroup>
                <Stat label="Portfolio value" value="£124,518" provenance="measured" detail={<Delta value={0.045} />} />
            </StatGroup>,
        )
        const term = screen.getByRole('term')
        expect(term).toHaveTextContent('Portfolio value')
        expect(term).toHaveTextContent('measured')
        expect(screen.getAllByRole('definition')[0]).toHaveTextContent('£124,518')
        expect(screen.getByText('+4.5%')).toBeInTheDocument()
    })

    it('shows losses with a minus sign and the loss style', () => {
        render(<Delta value={-310} format="money" />)
        const el = screen.getByText('−£310')
        expect(el.className).toMatch(/loss/)
    })

    it('keeps gains in ink with a plus sign', () => {
        render(<Delta value={0.012} format="pp" />)
        expect(screen.getByText('+1.2 pp').className).not.toMatch(/loss/)
    })

    it('renders a missing delta as an em dash without the loss style', () => {
        render(<Delta value={null} />)
        expect(screen.getByText('—').className).not.toMatch(/loss/)
    })
})

describe('Tag and Provenance', () => {
    it('always carries words, not just colour', () => {
        render(<Tag tone="warn">Rebalance due</Tag>)
        expect(screen.getByText('Rebalance due')).toBeInTheDocument()
    })

    it.each(['measured', 'simulated', 'estimated'] as const)('explains what %s means', (kind) => {
        render(<Provenance kind={kind} />)
        expect(screen.getByText(kind)).toHaveAttribute('title', PROVENANCE_MEANING[kind])
    })
})

describe('ErrorBoundary', () => {
    function Boom(): never {
        throw new Error('chart exploded')
    }

    it('replaces a crashed tree with an explanation and a way out', () => {
        vi.spyOn(console, 'error').mockImplementation(() => {})
        render(
            <ErrorBoundary>
                <Boom />
            </ErrorBoundary>,
        )
        expect(screen.getByRole('alert')).toHaveTextContent('This page could not be displayed.')
        expect(screen.getByRole('button', { name: 'Reload the page' })).toBeInTheDocument()
        expect(screen.getByText('chart exploded')).toBeInTheDocument()
        vi.mocked(console.error).mockRestore()
    })

    it('renders children when nothing throws', () => {
        render(
            <ErrorBoundary>
                <p>Fine</p>
            </ErrorBoundary>,
        )
        expect(screen.getByText('Fine')).toBeInTheDocument()
    })

    it('recovers when its reset key changes, as it does on navigating away', () => {
        vi.spyOn(console, 'error').mockImplementation(() => {})
        const view = render(
            <ErrorBoundary resetKey="/broken">
                <Boom />
            </ErrorBoundary>,
        )
        expect(screen.getByRole('alert')).toBeInTheDocument()
        view.rerender(
            <ErrorBoundary resetKey="/fine">
                <p>Fine</p>
            </ErrorBoundary>,
        )
        expect(screen.getByText('Fine')).toBeInTheDocument()
        vi.mocked(console.error).mockRestore()
    })

    it('keeps a healthy tree mounted when its reset key changes', () => {
        const view = render(
            <ErrorBoundary resetKey="/a">
                <input aria-label="Kept" defaultValue="typed" />
            </ErrorBoundary>,
        )
        const input = screen.getByRole('textbox', { name: 'Kept' })
        view.rerender(
            <ErrorBoundary resetKey="/b">
                <input aria-label="Kept" defaultValue="typed" />
            </ErrorBoundary>,
        )
        expect(screen.getByRole('textbox', { name: 'Kept' })).toBe(input)
    })
})
