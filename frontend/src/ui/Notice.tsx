import { Info, WarningCircle, Warning } from '@phosphor-icons/react'
import { clsx } from 'clsx'
import { useEffect, useRef, type ReactNode } from 'react'
import styles from './Notice.module.css'

export type NoticeTone = 'info' | 'warn' | 'error'

export interface NoticeProps {
    tone?: NoticeTone
    title?: ReactNode
    /** A button or link that resolves it, e.g. "Try again". */
    action?: ReactNode
    className?: string
    children?: ReactNode
}

const ICONS = { info: Info, warn: Warning, error: WarningCircle } as const

/**
 * A short message in the flow of the page. Errors are announced as alerts;
 * information and cautions are not, because they are there on arrival.
 */
export function Notice({ tone = 'info', title, action, className, children }: NoticeProps) {
    const Icon = ICONS[tone]
    return (
        <div className={clsx(styles.notice, styles[tone], className)} role={tone === 'error' ? 'alert' : undefined}>
            <Icon className={styles.icon} aria-hidden="true" weight="bold" />
            <div className={styles.body}>
                {title && <p className={styles.title}>{title}</p>}
                {children && <div className={styles.text}>{children}</div>}
                {action && <div className={styles.action}>{action}</div>}
            </div>
        </div>
    )
}

export interface FieldError {
    /** The id of the control to jump to. */
    id: string
    message: string
}

/**
 * The problems on a form, listed at the top with links to each control.
 * It takes focus when it appears, so keyboard and screen-reader users land on it.
 */
export function ErrorSummary({ errors, title = 'Check these answers' }: { errors: readonly FieldError[]; title?: string }) {
    const ref = useRef<HTMLDivElement>(null)
    const signature = errors.map((e) => e.id).join('|')

    useEffect(() => {
        if (signature) ref.current?.focus()
    }, [signature])

    if (errors.length === 0) return null
    return (
        <div ref={ref} className={clsx(styles.notice, styles.error, styles.summary)} role="alert" tabIndex={-1}>
            <WarningCircle className={styles.icon} aria-hidden="true" weight="bold" />
            <div className={styles.body}>
                <p className={styles.title}>{title}</p>
                <ul className={styles.list}>
                    {errors.map((e) => (
                        <li key={e.id}>
                            <a
                                href={`#${e.id}`}
                                onClick={(event) => {
                                    event.preventDefault()
                                    const target = document.getElementById(e.id)
                                    target?.focus()
                                    target?.scrollIntoView({ block: 'center' })
                                }}
                            >
                                {e.message}
                            </a>
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    )
}
