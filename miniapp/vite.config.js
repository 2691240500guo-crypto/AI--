import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uni()],
  server: {
    host: '127.0.0.1',
    port: 5174,
    strictPort: true
  }
})