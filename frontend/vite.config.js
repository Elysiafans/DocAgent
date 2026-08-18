import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发:前端 5173,后端 8000;协议入口 /mcp /a2a 一并代理
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/mcp': 'http://localhost:8000',
      '/a2a': 'http://localhost:8000',
    },
  },
})
