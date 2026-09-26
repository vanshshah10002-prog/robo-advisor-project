import { Component, type ErrorInfo, type ReactNode } from 'react'
import styles from './ErrorBoundary.module.css'

interface Props {
    children: ReactNode
}

interface State {
    error: Error | null
}

/**
 * Last line of defence: a render error shows a plain explanation and a way
 * back instead of a blank page. Data errors are handled where they occur
 * (react-query states); this only catches bugs.
 */
export class ErrorBoundary extends Component<Props, State> {
    state: State = { error: null }

    static getDerivedStateFromError(error: Error): State {
        return { error }
    }

    componentDidCatch(error: Error, info: ErrorInfo): void {
        console.error('Unhandled render error', error, info.componentStack)
    }

    private readonly reload = () => {
        window.location.reload()
    }

    render() {
        if (!this.state.error) return this.props.children
        return (
            <main className={styles.root} role="alert">
                <p className="label">Something went wrong</p>
                <h1 className={styles.title}>This page could not be displayed.</h1>
                <p className={styles.body}>
                    Your portfolio and its records are stored on the server and are not affected. Reloading
                    usually fixes this; if it keeps happening, the details below will help.
                </p>
                <div className={styles.actions}>
                    <button type="button" className={styles.primary} onClick={this.reload}>
                        Reload the page
                    </button>
                    <a href="/">Go to the start</a>
                </div>
                <details className={styles.details}>
                    <summary>Technical details</summary>
                    <pre>{this.state.error.message}</pre>
                </details>
            </main>
        )
    }
}
