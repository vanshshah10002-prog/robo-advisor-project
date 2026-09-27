import { humanise } from '@/lib/names'
import { useAssetClasses, useEtfs } from './queries'

/** Registry names for asset classes, falling back to a readable form of the id while they load. */
export function useAssetClassNames(): (id: string) => string {
    const classes = useAssetClasses()
    const byId = new Map((classes.data ?? []).map((c) => [c.id, c.name]))
    return (id) => byId.get(id) ?? humanise(id)
}

/** Fund names by ticker, falling back to the ticker itself. */
export function useFundNames(): (ticker: string) => string {
    const etfs = useEtfs()
    const byTicker = new Map((etfs.data ?? []).map((e) => [e.ticker, e.name]))
    return (ticker) => byTicker.get(ticker) ?? ticker
}
