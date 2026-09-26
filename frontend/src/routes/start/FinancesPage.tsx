import { useNavigate } from 'react-router-dom'
import { useSubmitRiskProfile } from '@/api/queries'
import type { ObjectiveInputs } from '@/api/schemas'
import { useIdentity } from '@/store/session'
import { ChoiceGroup } from '@/ui/ChoiceGroup'
import { Notice } from '@/ui/Notice'
import { MoneyField } from '@/ui/MoneyField'
import { Question } from './fields'
import { buildProfileRequest, EMPLOYMENT, fieldId, firstIncomplete, RESULT_PATH, SECTIONS } from './model'
import { QuestionsGate } from './QuestionsGate'
import { SectionForm } from './SectionForm'
import { useSection } from './useSection'

const SECTION = SECTIONS[2]
const ISA_OPTIONS = [
    { value: 'yes', label: 'Yes, an ISA' },
    { value: 'no', label: 'No, a general account' },
] as const

/**
 * Step 3: what you could afford to lose. Continuing sends every answer to
 * the risk profiler. If it fails, the page says so and keeps the answers;
 * nothing is made up in its place.
 */
export default function FinancesPage() {
    const navigate = useNavigate()
    const setUser = useIdentity((s) => s.setUser)
    const submit = useSubmitRiskProfile()
    const { draft, problems, errorFor, attempt, sentBack } = useSection('finances')
    const setObjective = (patch: Partial<ObjectiveInputs>) => draft.update({ objective: { ...draft.objective, ...patch } })

    const onValid = () => {
        const incomplete = firstIncomplete(draft)
        if (incomplete && incomplete.key !== 'finances') {
            navigate(incomplete.path, { state: { incomplete: true } })
            return
        }
        const request = buildProfileRequest(draft)
        if (!request) return
        submit.mutate(request, {
            onSuccess: (profile) => {
                setUser(profile.user_id)
                draft.update({ chosenRiskScore: null })
                navigate(RESULT_PATH)
            },
        })
    }

    return (
        <SectionForm
            section="finances"
            problems={problems}
            sentBack={sentBack}
            submitLabel="See my risk level"
            pending={submit.isPending}
            onContinue={() => attempt(onValid)}
            footer={
                submit.isError && (
                    <Notice tone="error" title="We could not work out your risk level">
                        {submit.error.message} Your answers are kept; try again in a moment.
                    </Notice>
                )
            }
        >
            <MoneyField
                id={fieldId.amount}
                label="How much do you want to invest now?"
                hint="You can add a monthly amount on the next screen."
                value={draft.investmentAmount}
                onChange={(v) => draft.update({ investmentAmount: v })}
                error={errorFor(fieldId.amount)}
            />
            <MoneyField
                id={fieldId.savings}
                label="Your savings and investments in total"
                hint="Include the amount above. Leave out your home and your pension."
                value={draft.objective.total_investable_assets}
                onChange={(v) => setObjective({ total_investable_assets: v ?? undefined })}
                error={errorFor(fieldId.savings)}
            />
            <MoneyField
                id={fieldId.income}
                label="Monthly income after tax"
                value={draft.objective.monthly_income}
                onChange={(v) => setObjective({ monthly_income: v ?? undefined })}
                error={errorFor(fieldId.income)}
            />
            <MoneyField
                id={fieldId.spending}
                label="Monthly spending"
                hint="Rent or mortgage, bills and everyday costs."
                value={draft.objective.monthly_expenses}
                onChange={(v) => setObjective({ monthly_expenses: v ?? undefined })}
                error={errorFor(fieldId.spending)}
            />
            <ChoiceGroup
                id={fieldId.employment}
                legend="How do you earn your living?"
                inline
                options={EMPLOYMENT}
                value={draft.objective.employment_type}
                onChange={(v) => setObjective({ employment_type: v })}
                error={errorFor(fieldId.employment)}
            />
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
            <ChoiceGroup
                id={fieldId.isa}
                legend="Will you invest through a Stocks and Shares ISA?"
                hint="An ISA keeps gains and income free of UK tax, up to £20,000 a year."
                inline
                options={ISA_OPTIONS}
                value={draft.usesIsa === null ? null : draft.usesIsa ? 'yes' : 'no'}
                onChange={(v) => draft.update({ usesIsa: v === 'yes' })}
                error={errorFor(fieldId.isa)}
            />
        </SectionForm>
    )
}
