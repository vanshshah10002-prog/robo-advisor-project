/**
 * The track record in plain words. Built from the figures, whichever way
 * they fall: if the simple benchmark did better, the sentence says so.
 */
import type { TrackRecord } from '@/api/schemas'
import { date, money, percent } from '@/lib/format'

export function trackRecordSentence(r: TrackRecord): string {
    const { strategy: s, benchmark: b } = r
    const opening = `At level ${r.risk}, ${money(r.initial)} run through these rules from ${date(r.start)} would have ended at ${money(s.end_value)}, or ${percent(s.cagr)} a year.`
    const returns =
        s.cagr >= b.cagr
            ? `That beat a simple two-fund portfolio with the same share in shares, which made ${percent(b.cagr)} a year.`
            : `A simple two-fund portfolio with the same share in shares did better, at ${percent(b.cagr)} a year.`
    const falls = `At its worst it was ${percent(-s.max_drawdown)} below its previous high, against ${percent(-b.max_drawdown)} for the two-fund portfolio.`
    return `${opening} ${returns} ${falls}`
}
