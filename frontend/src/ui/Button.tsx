import { clsx } from 'clsx'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router-dom'
import styles from './Button.module.css'

export type ButtonVariant = 'primary' | 'secondary' | 'quiet'
export type ButtonSize = 'md' | 'sm'

interface CommonProps {
    variant?: ButtonVariant
    size?: ButtonSize
    /** Icon placed after the label, e.g. an arrow on a forward action. */
    trailingIcon?: ReactNode
    leadingIcon?: ReactNode
    children: ReactNode
}

function classes(variant: ButtonVariant, size: ButtonSize, className?: string) {
    return clsx(styles.button, styles[variant], size === 'sm' && styles.sm, className)
}

export interface ButtonProps extends CommonProps, Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
    /** Shows a working state: the button keeps its width, announces itself busy, and ignores clicks. */
    loading?: boolean
}

export function Button({
    variant = 'primary',
    size = 'md',
    loading = false,
    leadingIcon,
    trailingIcon,
    children,
    className,
    disabled,
    type = 'button',
    onClick,
    ...rest
}: ButtonProps) {
    return (
        <button
            {...rest}
            type={type}
            className={classes(variant, size, className)}
            disabled={disabled}
            aria-busy={loading || undefined}
            aria-disabled={loading || undefined}
            data-loading={loading || undefined}
            onClick={loading ? (e) => e.preventDefault() : onClick}
        >
            {leadingIcon && <span className={styles.icon} aria-hidden="true">{leadingIcon}</span>}
            <span className={styles.label}>{children}</span>
            {trailingIcon && <span className={styles.icon} aria-hidden="true">{trailingIcon}</span>}
            {loading && <span className={styles.spinner} aria-hidden="true" />}
        </button>
    )
}

export interface ButtonLinkProps extends CommonProps, Omit<LinkProps, 'children'> {}

/** Navigation that looks like a button. Renders a real link, so it opens in a new tab and reads as a link. */
export function ButtonLink({
    variant = 'primary',
    size = 'md',
    leadingIcon,
    trailingIcon,
    children,
    className,
    ...rest
}: ButtonLinkProps) {
    return (
        <Link {...rest} className={classes(variant, size, className)}>
            {leadingIcon && <span className={styles.icon} aria-hidden="true">{leadingIcon}</span>}
            <span className={styles.label}>{children}</span>
            {trailingIcon && <span className={styles.icon} aria-hidden="true">{trailingIcon}</span>}
        </Link>
    )
}
