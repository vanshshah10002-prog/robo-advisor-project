import { useNavigate } from 'react-router-dom'
import { Question } from './fields'
import { fieldId, SECTIONS } from './model'
import { QuestionsGate } from './QuestionsGate'
import { SectionForm } from './SectionForm'
import { useSection } from './useSection'

const SECTION = SECTIONS[1]

/** Step 2: how you feel when prices fall, and what you know about investing. */
export default function LossesPage() {
    const navigate = useNavigate()
    const { draft, problems, errorFor, attempt, sentBack } = useSection('losses')

    return (
        <SectionForm section="losses" problems={problems} sentBack={sentBack} onContinue={() => attempt(() => navigate(SECTIONS[2].path))}>
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
