import { clsx } from 'clsx'
import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from 'react'
import { WarningCircle } from '@phosphor-icons/react'
import styles from './Field.module.css'

/** Props a control needs to be tied to its label, hint and error. */
export interface ControlProps {
    id: string
    'aria-describedby': string | undefined
    'aria-invalid': true | undefined
}

export interface FieldProps {
    /** Fixed id for the control, so an error summary can link to it. Generated when omitted. */
    id?: string
    label: ReactNode
    /** Plain-English help shown under the label, e.g. why we ask. */
    hint?: ReactNode
    /** Shown in place of nothing when the value is invalid; announced to screen readers. */
    error?: string
    optional?: boolean
    className?: string
    children: (control: ControlProps) => ReactNode
}

export function Field({ id: fixedId, label, hint, error, optional = false, className, children }: FieldProps) {
    const generated = useId()
    const id = fixedId ?? generated
    const hintId = hint ? `${id}-hint` : undefined
    const errorId = error ? `${id}-error` : undefined
    const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined

    return (
        <div className={clsx(styles.field, error && styles.invalid, className)}>
            <label className={styles.label} htmlFor={id}>
                {label}
                {optional && <span className={styles.optional}> (optional)</span>}
            </label>
            {hint && (
                <p id={hintId} className={styles.hint}>
                    {hint}
                </p>
            )}
            {children({ id, 'aria-describedby': describedBy, 'aria-invalid': error ? true : undefined })}
            {error && (
                <p id={errorId} className={styles.error}>
                    <WarningCircle aria-hidden="true" weight="bold" />
                    <span>{error}</span>
                </p>
            )}
        </div>
    )
}

export interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
    /** Fixed text before the value, e.g. "£". Visual only: the label must name the unit too. */
    prefix?: string
    /** Fixed text after the value, e.g. "% a year" or "years". */
    suffix?: string
}

export const TextInput = forwardRef<HTMLInputElement, TextInputProps>(function TextInput(
    { prefix, suffix, className, ...rest },
    ref,
) {
    return (
        <div className={clsx(styles.control, className)}>
            {prefix && (
                <span className={styles.affix} aria-hidden="true">
                    {prefix}
                </span>
            )}
            <input ref={ref} className={styles.input} {...rest} />
            {suffix && (
                <span className={styles.affix} aria-hidden="true">
                    {suffix}
                </span>
            )}
        </div>
    )
})
