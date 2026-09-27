/**
 * The track record in plain words. Built from the figures, whichever way
 * they fall: if the benchmark did better, the sentence says so.
 */
import type { TrackRecord } from '@/api/schemas'
import { date, money, percent } from '@/lib/format'

const share = (weight: number) => percent(weight, 0)

/** "50% VWRL.L", then "50% AGBP.L", joined as given. */
const benchmarkMix = (r: TrackRecord, joiner: string) => r.benchmark_funds.map((f) => `${share(f.weight)} ${f.ticker}`).join(joiner)

/** "Benchmark: 50% VWRL.L + 50% AGBP.L", for a chart's key. */
export const benchmarkLabel = (r: TrackRecord) => `Benchmark: ${benchmarkMix(r, ' + ')}`

/** Each of the benchmark's funds by its full name, for the summary of a chart. */
export const benchmarkNames = (r: TrackRecord) => r.benchmark_funds.map((f) => `${share(f.weight)} in ${f.name} (${f.ticker})`).join(' and ')

export function trackRecordSentence(r: TrackRecord): string {
    const { strategy: s, benchmark: b } = r
    const opening =
        `In the backtest at risk level ${r.risk}, ${money(r.initial)} invested from ${date(r.start)} would have ended at ${money(s.end_value)}, ` +
        `an annualised return of ${percent(s.cagr)}.`
    const returns =
        s.cagr >= b.cagr
            ? `That beat a benchmark of ${benchmarkMix(r, ' and ')}, which returned ${percent(b.cagr)} a year.`
            : `A benchmark of ${benchmarkMix(r, ' and ')} did better, at ${percent(b.cagr)} a year.`
    const falls = `The strategy’s maximum drawdown was ${percent(-s.max_drawdown)}, against ${percent(-b.max_drawdown)} for the benchmark.`
    return `${opening} ${returns} ${falls}`
}
