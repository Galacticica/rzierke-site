import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import * as path from 'node:path'

export default defineConfig({
    root: path.resolve('./static'),
    plugins: [tailwindcss()],
    base: '/static/',
    server: {
        host: '0.0.0.0',
        port: 5173,
        strictPort: true,
        hmr: {
            host: 'localhost',
            clientPort: 5173,
        },
    },
    build: {
        manifest: "manifest.json",
        outDir: path.resolve('./static/dist'),
        rollupOptions: {
            input:  path.resolve('./static/src/app.js'),
        }
    }
});