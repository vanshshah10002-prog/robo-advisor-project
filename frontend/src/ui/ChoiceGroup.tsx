import { WarningCircle } from '@phosphor-icons/react'
import { clsx } from 'clsx'
import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react'
import styles from './ChoiceGroup.module.css'
import { TipText } from './Term'
import { useTip } from './useTip'

export interface ChoiceOption<V extends string | number> {
    value: V
    label: ReactNode
    /** A short explanation, shown on hover or focus and read as the radio's description. */
    tip?: string
}

export interface ChoiceGroupProps<V extends string | number> {
    /** Given to the first option, so an error summary can link to the question. */
    id?: string
    legend: ReactNode
    hint?: ReactNode
    error?: string
    options: readonly ChoiceOption<V>[]
    value: V | null | undefined
    onChange: (value: V) => void
    /** Show 1, 2, 3… beside each option; the number keys pick it. */
    numbered?: boolean
    /** Short options sit side by side. */
    inline?: boolean
    className?: string
}

const DIGIT = /^[1-9]$/

/**
 * One answer from a short list, as real radio buttons: Tab reaches the group,
 * arrows move within it, and with `numbered` the keys 1–9 pick directly.
 * Every option is a full-width target at least 44px tall.
 */
export function ChoiceGroup<V extends string | number>({
    id,
    legend,
    hint,
    error,
    options,
    value,
    onChange,
    numbered = false,
    inline = false,
    className,
}: ChoiceGroupProps<V>) {
    const generated = useId()
    const base = id ?? generated
    const hintId = hint ? `${base}-hint` : undefined
    const errorId = error ? `${base}-error` : undefined
    const inputs = useRef<(HTMLInputElement | null)[]>([])

    const onKeyDown = (e: KeyboardEvent) => {
        if (!numbered || !DIGIT.test(e.key) || e.altKey || e.ctrlKey || e.metaKey) return
        const index = Number(e.key) - 1
        if (index >= options.length) return
        e.preventDefault()
        onChange(options[index].value)
        inputs.current[index]?.focus()
    }

    return (
        <fieldset
            className={clsx(styles.group, error && styles.invalid, className)}
            aria-describedby={[hintId, errorId].filter(Boolean).join(' ') || undefined}
            onKeyDown={onKeyDown}
        >
            <legend className={styles.legend}>{legend}</legend>
            {hint && (
                <p id={hintId} className={styles.hint}>
                    {hint}
                </p>
            )}
            {error && (
                <p id={errorId} className={styles.error}>
                    <WarningCircle aria-hidden="true" weight="bold" />
                    <span>{error}</span>
                </p>
            )}
            <div className={clsx(styles.options, inline && styles.inline)}>
                {options.map((option, i) => (
                    <Choice
                        key={String(option.value)}
                        option={option}
                        id={i === 0 ? base : undefined}
                        name={base}
                        number={numbered ? i + 1 : undefined}
                        checked={value === option.value}
                        onChange={() => onChange(option.value)}
                        inputRef={(el) => {
                            inputs.current[i] = el
                        }}
                    />
                ))}
            </div>
        </fieldset>
    )
}

interface ChoiceProps<V extends string | number> {
    option: ChoiceOption<V>
    id?: string
    name: string
    number?: number
    checked: boolean
    onChange: () => void
    inputRef: (el: HTMLInputElement | null) => void
}

/**
 * One option. Its tip sits beside the label rather than in it, so clicking
 * the tip never picks the option, and it opens while the option is hovered
 * or its radio has focus.
 */
function Choice<V extends string | number>({ option, id, name, number, checked, onChange, inputRef }: ChoiceProps<V>) {
    const tip = useTip()
    return (
        <>
            <label className={styles.option} {...(option.tip ? tip.anchor : {})}>
                <input
                    ref={inputRef}
                    id={id}
                    type="radio"
                    name={name}
                    className={styles.radio}
                    checked={checked}
                    onChange={onChange}
                    aria-describedby={option.tip ? tip.id : undefined}
                />
                {number !== undefined && (
                    <span className={styles.number} aria-hidden="true">
                        {number}
                    </span>
                )}
                <span className={styles.text}>{option.label}</span>
            </label>
            {option.tip && (
                <TipText id={tip.id} open={tip.open} below={tip.below} style={tip.style}>
                    {option.tip}
                </TipText>
            )}
        </>
    )
}
