import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const fromHere = (p: string) => fileURLToPath(new URL(p, import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    fs: {
      // Only what the site needs from outside this folder: product photos and the two catalogue
      // exports. The database (password hashes), users.json and test logins must never be served.
      allow: [
        fromHere('./'),
        fromHere('../data/products'),
        fromHere('../outputs/catalogue.json'),
        fromHere('../outputs/inventory.json'),
      ],
      deny: ['.env', '.env.*', '*.{crt,pem}', '**/*.db', '**/test_accounts.md', '**/users.json'],
    },
    // The FastAPI backend runs on port 8000 (override with API_TARGET). /media serves the
    // product photos referenced by chat cards (ProductCard.image_url).
    proxy: {
      '/api': process.env.API_TARGET ?? 'http://127.0.0.1:8000',
      '/media': process.env.API_TARGET ?? 'http://127.0.0.1:8000',
    },
  },
})
