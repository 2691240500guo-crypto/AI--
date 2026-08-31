<template>
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'
import { useUserStore } from '@/stores/user'

// 应用启动时恢复菜单：刷新页面后 Pinia store 重置，token 仍在 sessionStorage，
// 但 menus/perms 为空，需要重新拉一次以渲染侧边栏和动态路由
onMounted(() => {
  const user = useUserStore()
  if (user.token && user.menus.length === 0) {
    user.loadMenus()
  }
})
</script>