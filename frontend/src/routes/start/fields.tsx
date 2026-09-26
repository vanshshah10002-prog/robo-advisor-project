import type { QuizQuestion } from '@/api/schemas'
import { ChoiceGroup } from '@/ui/ChoiceGroup'
import { fieldId } from './model'

/** Why we ask, for the questions where it is not obvious. */
const HINTS: Record<number, string> = {
    4: 'Roughly, counting everything you own. Your home and pension included.',
    6: 'Money you could reach within a week without selling investments.',
    9: 'Before inflation. Higher expectations need more risk to meet.',
}

interface QuestionProps {
    question: QuizQuestion
    value: number | undefined
    onChange: (answer: number) => void
    error?: string
}

/** A questionnaire item as a numbered choice: the keys 1–5 answer it. */
export function Question({ question, value, onChange, error }: QuestionProps) {
    return (
        <ChoiceGroup
            id={fieldId.question(question.id)}
            legend={question.text}
            hint={HINTS[question.id]}
            error={error}
            numbered
            options={question.options.map((label, i) => ({ value: i + 1, label }))}
            value={value ?? null}
            onChange={onChange}
        />
    )
}
