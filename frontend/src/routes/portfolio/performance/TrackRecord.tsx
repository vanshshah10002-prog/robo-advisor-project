import { useTrackRecord } from '@/api/queries'
import { level, nearestTested } from '@/lib/risk'
import { Term } from '@/ui/Term'
import { trackRecordSentence } from '../../landing/evidence'
import { TrackRecordChart } from '../../TrackRecordChart'
import styles from '../Portfolio.module.css'

/**
 * The same rules run over the past five years at this portfolio's level:
 * simulated, not this portfolio's own history, and labelled so.
 */
export function TrackRecord({ risk }: { risk: number | null }) {
    const tested = risk === null ? null : nearestTested(risk)
    const record = useTrackRecord(tested)
    if (risk === null || tested === null) return null

    return (
        <section className={styles.subsection} aria-labelledby="record-title">
            <h2 id="record-title" className={styles.sectionTitle}>
                This strategy’s backtest at risk level {tested}
            </h2>
            <p className={styles.note}>
                A <Term explain="backtest">backtest</Term>, not this portfolio's history: the same construction rules run on past prices, deciding
                each date only with what was known then.{risk !== tested && ` Level ${tested} is the nearest tested level to this portfolio's ${level(risk)}.`}{' '}
                {record.data && trackRecordSentence(record.data)}
            </p>
            <TrackRecordChart record={record} />
        </section>
    )
}
