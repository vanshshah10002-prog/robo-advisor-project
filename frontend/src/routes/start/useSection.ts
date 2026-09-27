import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useOnboardingDraft } from '@/store/session'
import { validateSection, type Problem, type SectionKey } from './model'

/** Router state set when the last section sends someone back to finish an earlier one. */
export interface IncompleteState {
    incomplete: true
}

const isIncomplete = (state: unknown): state is IncompleteState =>
    typeof state === 'object' && state !== null && (state as IncompleteState).incomplete === true

/**
 * Validation for one onboarding section. Problems appear only after the
 * first attempt to continue, then update live as answers are fixed.
 */
export function useSection(key: SectionKey) {
    const draft = useOnboardingDraft()
    const { state } = useLocation()
    const [attempted, setAttempted] = useState(isIncomplete(state))
    const problems: Problem[] = attempted ? validateSection(key, draft) : []
    const errorFor = (id: string) => problems.find((p) => p.id === id)?.message

    const attempt = (onValid: () => void) => {
        setAttempted(true)
        if (validateSection(key, draft).length === 0) onValid()
    }

    return { draft, problems, errorFor, attempt, sentBack: isIncomplete(state) }
}
