import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import basicSsl from '@vitejs/plugin-basic-ssl'

const useHttps = process.env.HTTPS === 'true'

export default defineConfig({
    plugins: [
        react(),
        useHttps ? basicSsl() : null
    ],
    server: {
        port: 1337,
        host: true,
        https: useHttps
    }
})
