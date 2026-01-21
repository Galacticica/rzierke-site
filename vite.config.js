import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import * as path from 'node:path'

export default defineConfig({
    plugins: [tailwindcss()],
    base: '/static/',
    build: {
        manifest: "manifest.json",
        outDir: path.resolve('./static/dist'),
        rollupOptions: {
            input:  path.resolve('./static/src/app.js'),
        }
    }
});