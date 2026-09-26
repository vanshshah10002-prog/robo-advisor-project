/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        port: 5173,
        proxy: {
            // The backend mounts its routes under /api, so no rewrite is needed.
            '/api': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
            },
        },
    },
    test: {
        environment: 'jsdom',
        setupFiles: ['./src/test/setup.ts'],
        include: ['src/**/*.test.{ts,tsx}'],
        // Only the token sheet is read in tests (as ?raw); component CSS is skipped.
        css: { include: [/styles\/tokens\.css/] },
        coverage: {
            provider: 'v8',
            include: [
                'src/api/http.ts',
                'src/api/endpoints.ts',
                'src/api/queries.ts',
                'src/charts/**',
                'src/lib/**',
                'src/routes/AppShell.tsx',
                'src/store/session.ts',
                'src/ui/**',
            ],
            exclude: ['**/*.test.{ts,tsx}'],
            thresholds: { lines: 80, functions: 80, branches: 80, statements: 80 },
        },
    },
})
