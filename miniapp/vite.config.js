import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uni()],
  server: {
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
    // H5 开发：把 /api 代理到后端 FastAPI（8000），避免跨域并修正前缀到 /api/v1
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true }
    }
  }
})
