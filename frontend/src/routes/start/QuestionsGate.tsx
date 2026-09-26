import type { ReactNode } from 'react'
import { useQuizQuestions } from '@/api/queries'
import type { QuizQuestion } from '@/api/schemas'
import { Button } from '@/ui/Button'
import { Notice } from '@/ui/Notice'
import styles from './Start.module.css'

/**
 * Loads the questionnaire once and hands the listed questions to its child.
 * If it cannot load, it says so and offers a retry; it never invents questions.
 */
export function QuestionsGate({ ids, children }: { ids: readonly number[]; children: (q: QuizQuestion[]) => ReactNode }) {
    const quiz = useQuizQuestions()

    if (quiz.isPending) {
        return (
            <p className={styles.loading} aria-busy="true">
                Loading the questions…
            </p>
        )
    }
    if (quiz.isError) {
        return (
            <Notice
                tone="error"
                title="The questions did not load"
                action={
                    <Button size="sm" variant="secondary" onClick={() => quiz.refetch()}>
                        Try again
                    </Button>
                }
            >
                Check your connection. Nothing you have answered so far is lost.
            </Notice>
        )
    }
    const byId = new Map(quiz.data.map((q) => [q.id, q]))
    const questions = ids.flatMap((id) => {
        const q = byId.get(id)
        return q ? [q] : []
    })
    return <>{children(questions)}</>
}
