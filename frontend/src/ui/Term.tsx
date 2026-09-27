import { clsx } from 'clsx'
import type { CSSProperties, ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { GLOSSARY, type GlossaryTerm } from '@/lib/glossary'
import styles from './Term.module.css'
import { useTip } from './useTip'

/**
 * A financial term with its meaning a hover, tap or Tab away. The term is
 * underlined with dots and can take focus; its explanation is its
 * accessible description, so a screen reader announces it with the term,
 * and it is hidden from the reading order so it is never read twice.
 */
export function Term({ explain, children }: { explain: GlossaryTerm; children: ReactNode }) {
    const tip = useTip()
    return (
        <span className={styles.term} tabIndex={0} aria-describedby={tip.id} {...tip.anchor}>
            {children}
            <TipText id={tip.id} open={tip.open} below={tip.below} style={tip.style}>
                {GLOSSARY[explain]}
            </TipText>
        </span>
    )
}

interface TipTextProps {
    id: string
    open: boolean
    below: boolean
    style?: CSSProperties
    children: ReactNode
}

/**
 * The explanation itself, shared with the choices that carry one. It is
 * rendered into the body: an ancestor with a transform, such as a section
 * still holding its entrance animation, would otherwise become the box that
 * `position: fixed` is measured from. React events still pass through the
 * portal, so the pointer can move from the term onto its tip.
 */
export function TipText({ id, open, below, style, children }: TipTextProps) {
    return createPortal(
        <span id={id} className={clsx(styles.tip, below ? styles.below : styles.above)} style={style} hidden={!open} aria-hidden="true">
            {children}
        </span>,
        document.body,
    )
}
