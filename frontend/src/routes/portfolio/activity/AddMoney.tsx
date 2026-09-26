import { useState, type FormEvent } from 'react'
import { useContribute } from '@/api/queries'
import { money } from '@/lib/format'
import { Button } from '@/ui/Button'
import { MoneyField } from '@/ui/MoneyField'
import { Notice } from '@/ui/Notice'
import styles from '../Portfolio.module.css'

/** Pays money in and invests it where the portfolio is most underweight. */
export function AddMoney({ id }: { id: number }) {
    const contribute = useContribute(id)
    const [amount, setAmount] = useState<number | null>(null)
    const [tried, setTried] = useState(false)
    // A new key clears the field after a deposit.
    const [field, setField] = useState(0)
    const valid = amount !== null && amount > 0

    const submit = (e: FormEvent) => {
        e.preventDefault()
        setTried(true)
        if (!valid) return
        contribute.mutate(
            { amount_gbp: amount },
            {
                onSuccess: () => {
                    setAmount(null)
                    setTried(false)
                    setField((k) => k + 1)
                },
            },
        )
    }

    const done = contribute.data
    return (
        <section className={styles.panel} aria-labelledby="add-title">
            <h2 id="add-title" className={styles.sectionTitle}>
                Add money
            </h2>
            <p className={styles.note}>
                Recorded as money paid in, then invested where the portfolio is furthest below its targets. Model portfolio: no real money
                moves.
            </p>
            <form className={styles.panelForm} noValidate onSubmit={submit}>
                <MoneyField
                    key={field}
                    id="add-amount"
                    label="Amount to add"
                    value={amount}
                    onChange={setAmount}
                    error={tried && !valid ? 'Enter an amount above £0.' : undefined}
                />
                <Button type="submit" loading={contribute.isPending}>
                    {valid ? `Add ${money(amount)}` : 'Add money'}
                </Button>
            </form>
            <p className={styles.note} aria-live="polite">
                {done && `${money(done.deposited_gbp)} added and invested in ${done.buys.length} fund${done.buys.length === 1 ? '' : 's'}. The portfolio is now worth ${money(done.total_value)}.`}
            </p>
            {contribute.isError && (
                <Notice tone="error" title="The money was not added">
                    {contribute.error.message} Nothing was recorded.
                </Notice>
            )}
        </section>
    )
}
