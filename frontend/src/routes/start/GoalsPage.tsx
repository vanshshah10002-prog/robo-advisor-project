import { useNavigate } from 'react-router-dom'
import { parseWhole } from '@/lib/parse'
import { Field, TextInput } from '@/ui/Field'
import { Question } from './fields'
import { fieldId, MAX_HORIZON_YEARS, SECTIONS } from './model'
import { QuestionsGate } from './QuestionsGate'
import { SectionForm } from './SectionForm'
import { useSection } from './useSection'

const SECTION = SECTIONS[0]

/** Step 1: who you are, when you need the money, and what you hope for. */
export default function GoalsPage() {
    const navigate = useNavigate()
    const { draft, problems, errorFor, attempt, sentBack } = useSection('goals')
    const years = draft.objective.time_horizon_years

    return (
        <SectionForm section="goals" problems={problems} sentBack={sentBack} onContinue={() => attempt(() => navigate(SECTIONS[1].path))}>
            <Field id={fieldId.name} label="What should we call you?" hint="Your first name is enough." error={errorFor(fieldId.name)}>
                {(control) => (
                    <TextInput {...control} autoComplete="given-name" value={draft.name} onChange={(e) => draft.update({ name: e.target.value })} />
                )}
            </Field>
            <Field
                id={fieldId.horizon}
                label="When will you need most of this money?"
                hint={`In years from now, up to ${MAX_HORIZON_YEARS}. For retirement, count the years until you retire.`}
                error={errorFor(fieldId.horizon)}
            >
                {(control) => (
                    <TextInput
                        {...control}
                        inputMode="numeric"
                        suffix="years"
                        defaultValue={years === undefined ? '' : String(years)}
                        onChange={(e) =>
                            draft.update({ objective: { ...draft.objective, time_horizon_years: parseWhole(e.target.value) ?? undefined } })
                        }
                    />
                )}
            </Field>
            <QuestionsGate ids={SECTION.questionIds}>
                {(questions) =>
                    questions.map((q) => (
                        <Question
                            key={q.id}
                            question={q}
                            value={draft.answers[String(q.id)]}
                            onChange={(a) => draft.answer(q.id, a)}
                            error={errorFor(fieldId.question(q.id))}
                        />
                    ))
                }
            </QuestionsGate>
        </SectionForm>
    )
}
