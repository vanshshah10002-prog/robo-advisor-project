import { WarningCircle } from '@phosphor-icons/react'
import { clsx } from 'clsx'
import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react'
import styles from './ChoiceGroup.module.css'

export interface ChoiceOption<V extends string | number> {
    value: V
    label: ReactNode
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
                    <label key={String(option.value)} className={styles.option}>
                        <input
                            ref={(el) => {
                                inputs.current[i] = el
                            }}
                            id={i === 0 ? base : undefined}
                            type="radio"
                            name={base}
                            className={styles.radio}
                            checked={value === option.value}
                            onChange={() => onChange(option.value)}
                        />
                        {numbered && (
                            <span className={styles.number} aria-hidden="true">
                                {i + 1}
                            </span>
                        )}
                        <span className={styles.text}>{option.label}</span>
                    </label>
                ))}
            </div>
        </fieldset>
    )
}
