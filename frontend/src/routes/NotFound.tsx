import { usePageTitle } from '@/lib/usePageTitle'
import { ButtonLink } from '@/ui/Button'
import styles from './portfolio/Portfolio.module.css'

/** Any address the app does not know. */
export default function NotFound() {
    usePageTitle('Page not found')
    return (
        <article className={styles.page} aria-labelledby="not-found-title">
            <header className={styles.head}>
                <p className="label">Page not found</p>
                <h1 id="not-found-title" className={styles.title}>
                    There is nothing at this address
                </h1>
                <p className={styles.lead}>The link may be old: several pages moved when the app was rebuilt.</p>
            </header>
            <p>
                <ButtonLink to="/">Go to the start</ButtonLink>
            </p>
        </article>
    )
}
