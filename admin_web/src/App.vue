<template>
  <router-view />
</template>

<script setup>
import { onMounted, watch } from 'vue'
import { useUserStore } from '@/stores/user'

// 监听 token 变化：登录后或刷新页面时，只要 menus 为空就重新拉取
// （修复 BUG-015 后端已能返回父目录菜单，此处保证前端侧边栏能正确渲染）
onMounted(() => {
  const user = useUserStore()
  if (user.token && user.menus.length === 0) {
    user.loadMenus()
  }
})

const user = useUserStore()
// token 变化（登录成功）也触发 loadMenus，避免首次登录时机晚导致的空白
watch(() => user.token, (newToken) => {
  if (newToken && user.menus.length === 0) {
    user.loadMenus()
  }
})
</script>