import { useEffect } from 'react'

export const SITE_NAME = 'UK Robo Advisor'

/** Names the browser tab and history entry after the page: "Your goal · UK Robo Advisor". */
export function usePageTitle(title?: string) {
    useEffect(() => {
        document.title = title ? `${title} · ${SITE_NAME}` : SITE_NAME
    }, [title])
}
