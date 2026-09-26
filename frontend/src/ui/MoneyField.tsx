import { useState, type ReactNode } from 'react'
import { moneyInput, parseMoney } from '@/lib/parse'
import { Field, TextInput } from './Field'

export interface MoneyFieldProps {
    id: string
    label: ReactNode
    hint?: ReactNode
    value: number | null | undefined
    onChange: (value: number | null) => void
    /** Reported when the box is left empty, e.g. 0 for an optional amount. Null by default. */
    emptyValue?: number
    error?: string
}

/**
 * A pounds input that keeps what was typed ("50,0" stays "50,0" while
 * typing) and reports the parsed figure, or null when it is not one.
 */
export function MoneyField({ id, label, hint, value, onChange, emptyValue, error }: MoneyFieldProps) {
    const [text, setText] = useState(() => moneyInput(value))
    return (
        <Field id={id} label={label} hint={hint} error={error}>
            {(control) => (
                <TextInput
                    {...control}
                    prefix="£"
                    inputMode="decimal"
                    autoComplete="off"
                    value={text}
                    onChange={(e) => {
                        setText(e.target.value)
                        const blank = e.target.value.trim() === ''
                        onChange(blank && emptyValue !== undefined ? emptyValue : parseMoney(e.target.value))
                    }}
                />
            )}
        </Field>
    )
}
