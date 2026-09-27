import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import '@fontsource-variable/newsreader/opsz.css'
import '@fontsource-variable/newsreader/opsz-italic.css'
import '@fontsource-variable/schibsted-grotesk/wght.css'
import './styles/tokens.css'
import './styles/base.css'
import App from './App'
import { createQueryClient } from './api/queries'
import { ErrorBoundary } from './ui/ErrorBoundary'

const queryClient = createQueryClient()

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <ErrorBoundary>
            <QueryClientProvider client={queryClient}>
                <BrowserRouter>
                    <App />
                </BrowserRouter>
            </QueryClientProvider>
        </ErrorBoundary>
    </StrictMode>,
)
