<template>
  <router-view />
</template>

<script setup>
import { onMounted, watch } from 'vue'
import { useUserStore } from '@/stores/user'

// 关键修复：硬刷新页面后，Pinia store 重置但 token 仍在 sessionStorage。
// 必须从 sessionStorage 同步恢复 token，避免路由守卫误判"未登录"导致跳 /login
// （之前只读 store 默认值，导致硬刷新立即跳登录页，体验很差）
onMounted(() => {
  const user = useUserStore()
  // 二次确认：从 sessionStorage 同步到 store（避免初始化时序问题）
  const storedToken = sessionStorage.getItem('token')
  if (storedToken && !user.token) {
    user.token = storedToken
  }
  if (user.token && user.menus.length === 0) {
    user.loadMenus()
  }
})

const user = useUserStore()
// 监听 token 变化：登录后或刷新页面时，只要 menus 为空就重新拉取
watch(() => user.token, (newToken) => {
  if (newToken && user.menus.length === 0) {
    user.loadMenus()
  }
})
</script>