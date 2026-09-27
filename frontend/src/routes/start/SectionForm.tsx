import { ArrowLeft, ArrowRight } from '@phosphor-icons/react'
import type { FormEvent, ReactNode } from 'react'
import { usePageTitle } from '@/lib/usePageTitle'
import { Button, ButtonLink } from '@/ui/Button'
import { ErrorSummary, Notice } from '@/ui/Notice'
import { SECTIONS, type Problem, type SectionKey } from './model'
import styles from './Start.module.css'

interface SectionFormProps {
    section: SectionKey
    problems: readonly Problem[]
    onContinue: () => void
    sentBack?: boolean
    submitLabel?: string
    pending?: boolean
    /** Shown above the buttons, e.g. a failed submission. */
    footer?: ReactNode
    children: ReactNode
}

/** One section of onboarding: heading, error summary, fields, Back and Continue. */
export function SectionForm({ section, problems, onContinue, sentBack, submitLabel = 'Continue', pending, footer, children }: SectionFormProps) {
    const index = SECTIONS.findIndex((s) => s.key === section)
    const { title, intro } = SECTIONS[index]
    usePageTitle(title)
    const back = index > 0 ? SECTIONS[index - 1].path : '/'

    const onSubmit = (e: FormEvent) => {
        e.preventDefault()
        onContinue()
    }

    return (
        <form className={styles.form} noValidate onSubmit={onSubmit} aria-labelledby="section-title">
            <header className={styles.head}>
                <p className="label">
                    Step {index + 1} of {SECTIONS.length}
                </p>
                <h1 id="section-title" className={styles.title}>
                    {title}
                </h1>
                <p className={styles.intro}>{intro}</p>
            </header>
            {sentBack && problems.length > 0 && (
                <Notice tone="warn" title="A few answers are still needed here">
                    Finish this step, then carry on to the next.
                </Notice>
            )}
            <ErrorSummary errors={problems} />
            <div className={styles.fields}>{children}</div>
            {footer}
            <div className={styles.actions}>
                <ButtonLink to={back} variant="quiet" leadingIcon={<ArrowLeft weight="bold" />}>
                    Back
                </ButtonLink>
                <Button type="submit" loading={pending} trailingIcon={<ArrowRight weight="bold" />}>
                    {submitLabel}
                </Button>
            </div>
        </form>
    )
}
